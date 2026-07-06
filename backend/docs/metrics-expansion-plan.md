# Metrics Expansion Plan — Cash/Liquidity, Solvency/Leverage, Returns

## Why this exists

A spec-compliance check against the Senus PLC Board Report brief found
that 3 of the 5 required metric categories are **not captured anywhere
in the data model**, not just missing from a UI:

- **Cash & Liquidity** (cash runway, EBITDA→FCF bridge, working capital)
- **Solvency & Leverage** (debt, Debt Service Coverage Ratio)
- **Returns** (ROCE)

Also gap: no EBITDA margin (only raw EBITDA), no cost breakdown
(COGS/opex), and YoY/MoM growth today just diffs whichever two
documents were uploaded most recently rather than being calendar-aware.

The good news: the real source document
(`backend/uploads/Senus_HalfYearResultsDec2025_PR_V19032026 FINAL clean.pdf`)
already contains the raw ingredients for all of this — it was checked
directly:

- `Cash and bank debt balances were €735.1k and €76.5k respectively`
- `Cost of sales`, `Administrative expenses`, `Interest payable and
  similar expenses` (P&L lines)
- `Movements in working capital` (cash flow statement line)
- `Total Assets Less Current Liabilities` — this **is** capital employed
  in Irish/UK statutory account format, i.e. the ROCE denominator
- `Group Revenue increased 4.1% to €354.8k (HY25: €340.9k)` — an inline
  YoY comparative in narrative text

So this is an extraction-coverage and data-modeling gap, not a
data-availability problem. This plan closes it.

## Prompt to implement this

Use this as the task prompt for the implementation session:

---

> Extend the Senus Board Report backend's financial data model and
> extractor to support the three missing metric categories from the
> project brief: Cash & Liquidity, Solvency & Leverage, and Returns.
> Also add EBITDA margin, a basic cost breakdown, and make period
> comparisons calendar-aware instead of "latest two uploads." Full
> context for what already exists and why is in
> `backend/docs/backend-cleanup-2026-07.md` and
> `backend/docs/pipeline-service-improvements.md` — read those first so
> you don't reintroduce the narrative-leakage or missing-vs-zero bugs
> that were already fixed there.
>
> ### 1. Data model — new fields
>
> Add a new `BalanceSheetMetrics` model (own table, one row per
> `Document`, same pattern as `FinancialMetrics`) rather than bloating
> the existing table, since these are balance-sheet/cash-flow-sourced
> and conceptually distinct from the P&L snapshot `FinancialMetrics`
> already covers:
>
> - `total_debt: Optional[float]` (bank debt)
> - `interest_expense: Optional[float]`
> - `cost_of_sales: Optional[float]`
> - `administrative_expenses: Optional[float]`
> - `working_capital_change: Optional[float]` (from the cash flow
>   statement's "Movements in working capital" line)
> - `capital_employed: Optional[float]` (the balance sheet's "Total
>   Assets Less Current Liabilities" line — extract it directly rather
>   than deriving it, since it's reported as its own line item)
>
> Follow the existing `None`-means-missing convention from
> `FinancialMetricsExtractor` (see the "Fixed (round 2)" section of
> `pipeline-service-improvements.md` for why this matters) — do not
> default any of these to `0` at the extraction layer.
>
> ### 2. Extractor changes
>
> Extend `FinancialMetricsExtractor` (or add a sibling
> `BalanceSheetExtractor` if that keeps it cleaner — your call, but
> reuse the existing `_extract_section` / `_extract_table_value` /
> `_is_number` / `_to_number` helpers rather than duplicating parsing
> logic) to pull the new fields using the same section-isolation
> pattern already used for P&L/balance-sheet/cash-flow. Test against
> the real uploaded PDF, not just synthetic text — it's already in
> `backend/uploads/`.
>
> Known tricky bit: "Cash and bank debt balances were €735.1k and
> €76.5k respectively" puts two values in one narrative sentence rather
> than a table row — decide whether this needs a small narrative-regex
> fallback (like the existing `customers` extraction pattern) or
> whether the balance sheet table itself has the debt figure in
> structured form elsewhere in the document; check before guessing.
>
> ### 3. Computed (not stored) metrics
>
> Add to `MetricsService` (or wire up what's already there — see
> below):
>
> - `ebitda_margin = ebitda / revenue * 100` (revenue > 0 guard, same
>   pattern as `calculate_margins`)
> - **Cash runway**: `calculate_cash_runway(monthly_burn_rate,
>   cash_balance)` already exists in `MetricsService` but is dead code
>   — nothing calls it, and there's no burn-rate field to feed it.
>   Derive monthly burn rate from period-over-period cash change
>   (previous cash − current cash, divided by months between the two
>   snapshots) rather than adding a new stored field, since burn rate
>   isn't something a single filing reports directly.
> - **Debt Service Coverage Ratio**:
>   `EBITDA / (interest_expense + principal_repayments)`. Principal
>   repayments may not be separately disclosed in a half-year filing —
>   check the source before assuming it exists; a simplified
>   `EBITDA / interest_expense` interest-cover fallback may be the
>   honest answer if principal isn't broken out.
> - **ROCE**: `operating_profit / capital_employed * 100`. You'll need
>   operating profit — check whether that's derivable from
>   `revenue - cost_of_sales - administrative_expenses` or whether it's
>   reported as its own P&L line; use whichever is more reliable rather
>   than re-deriving something already stated.
> - `calculate_debt_ratios` and `calculate_margins` already exist in
>   `MetricsService` — audit them against the new fields' actual names
>   and either wire them up as-is or adjust their signatures; don't
>   leave a second, slightly-different set of duplicate calculations
>   sitting alongside them.
>
> ### 4. API surface
>
> Add a `BalanceSheetMetricsResponse` schema (`app/schemas/financial.py`
> or a new `app/schemas/balance_sheet.py`) and extend
> `GET /api/reports/{id}/dashboard` (or add a new endpoint if that one's
> getting overloaded — your call) to return the new computed metrics
> alongside the existing ones. Keep the existing response shape
> backward compatible — this is additive, not a breaking change.
>
> ### 5. YoY / MoM
>
> Current dashboard summary
> (`GET /metrics/dashboard/summary`) just diffs the latest two
> `FinancialMetrics` rows regardless of the actual time gap between
> them. Decide on and implement an actual period-aware comparison
> (e.g. compare against the snapshot closest to 12 months / 1 month
> before the latest one's `extracted_at`, not just "whatever came
> before it") — with a single filing today this can't be fully
> exercised, but the logic should be correct once more filings exist.
> Document the decision in code comments since "closest available
> snapshot to N months ago" has edge cases (no snapshot old enough,
> multiple candidates) worth being explicit about.
>
> ### 6. Channels / Bookings — explicitly out of scope for this pass
>
> Both require narrative/LLM-based extraction rather than
> table-structured parsing (the source PDF states bookings as
> "approx. €700k across 21 enterprise customers closed in the period"
> in prose, and channels as a passing narrative mention) — different
> extraction strategy than everything else here. Flag as a follow-up
> rather than bolting a fragile regex onto this pass.
>
> ### Verification
>
> Same standard as the rest of this codebase (see
> `backend-cleanup-2026-07.md` for the pattern): standalone scripts
> exercising the new extractor fields against the real uploaded PDF and
> against synthetic edge cases (missing debt, zero interest expense,
> revenue of 0 for margin/ROCE division guards), plus an end-to-end
> `TestClient` run through upload → dashboard confirming the new fields
> serialize correctly. Don't rely on pytest being sufficient on its own
> — verify against real data, per how the rest of this backend was
> validated.

---

## Acceptance checklist

- [x] `BalanceSheetMetrics` model + migration path -- table auto-creates
      via `Base.metadata.create_all` for a fresh DB; for the table that
      already existed in production before this (`financial_metrics`'s
      new `_prior` columns), added `_add_missing_columns` to
      `app/core/database.py` since `create_all` never alters an existing
      table's columns and there's no Alembic in this project. Verified
      against the real Railway Postgres DB, not just a fresh local one.
- [x] Extractor pulls debt, interest, cost of sales, admin expenses,
      working capital change, capital employed — verified against the
      real Senus PDF (`FinancialMetricsExtractor.extract_balance_sheet()`)
- [x] EBITDA margin, cash runway, a DSCR-or-interest-cover ratio, and
      ROCE all computed and exposed via the dashboard endpoint
      (`ebitda_margin`, `cash_runway`, `interest_cover`, `roce` on
      `GET /metrics/dashboard/summary`)
- [x] `calculate_debt_ratios`/`calculate_margins` either wired up or
      removed — no orphaned duplicate logic. Removed both:
      `calculate_margins` is fully superseded (gross/operating margin are
      now computed directly from extracted P&L lines in the extractor,
      more reliable than narrative regex); `calculate_debt_ratios` had no
      caller and no planned one (interest_cover covers the Solvency KPI
      slot instead).
- [ ] YoY/MoM comparison is calendar-aware, not "latest two uploads" --
      **not done as originally scoped**. Instead: the extractor now also
      captures each field's *own filing's* prior-period comparative
      column (e.g. "Turnover 354,813 340,931" -> `revenue`/`revenue_prior`),
      and `/dashboard/summary` falls back to that when there's no second
      DB row to diff against. This gives real YoY change today (this
      filing is literally Senus's first-ever results as a public company,
      so calendar-aware multi-filing comparison can't be exercised yet
      regardless) rather than leaving every KPI at a fake 0%/neutral.
      True calendar-aware comparison across multiple *uploaded* filings
      is still an open item once a second filing ever exists.
- [x] All new/changed extraction fields follow the `None` = missing,
      never silently `0`, convention
- [x] Verified against the real uploaded PDF, not just synthetic text --
      see `tests/test_financial_metrics_extractor.py::TestExtractAgainstRealFiling`
- [x] Backward-compatible API changes (existing dashboard consumers
      don't break) -- `history`/`change`/`trend` shape unchanged for the
      four original KPIs, new fields are additive
