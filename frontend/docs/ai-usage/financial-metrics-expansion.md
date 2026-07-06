# AI Usage — feature/financial-metrics-expansion

## What was built

Implements `backend/docs/metrics-expansion-plan.md` — the three metric
categories named in the assignment brief (Cash & Liquidity, Solvency &
Leverage, Returns) that had zero backing data anywhere in the system:

- New `BalanceSheetMetrics` table + a database migration helper (no
  Alembic in this project) to safely add new columns to the
  already-existing `financial_metrics` table in production.
- `FinancialMetricsExtractor` now *computes* EBITDA (operating result +
  depreciation add-back) and gross/operating margins from structured P&L
  lines, instead of searching for a literal "EBITDA" keyword that doesn't
  exist in the real filing, or fragile narrative-text regex for margins.
- The extractor also captures each field's prior-period comparative from
  the *same filing's* own comparison column, enabling real YoY change
  today rather than a permanent 0%/neutral.
- Four new computed ratios (`ebitda_margin`, `cash_runway`,
  `interest_cover`, `roce`) in `MetricsService`, exposed as new KPI cards
  on `GET /metrics/dashboard/summary` and the dashboard UI.
- Fixed a real, previously-latent bug in `calculate_change`: percentage
  change of two negative numbers (e.g. a narrowing loss) inverted sign
  versus the raw value's actual direction.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). This was
the largest and most exploratory branch so far, and depended heavily on
the user's own mid-session context: they shared the actual Assiduous
assignment brief partway through this session, which reframed the whole
project as a graded technical assessment rather than an ongoing product
build — that context is why this branch (previously deferred as
"future work" every prior branch) became the priority, ahead of items
like `feature/api-integration-layer` that aren't in the assignment brief
at all.

The user also caught a serious process error mid-branch: I assumed
running the backend locally would use a disposable local SQLite database
(matching the test suite's pattern), but `backend/.env`'s `DATABASE_URL`
actually pointed at the real Railway production Postgres. I had already
run a schema migration and a report regeneration against it, and
attempted (unsuccessfully, blocked by a foreign-key constraint) to delete
a document, before catching this and stopping. The user confirmed it was
fine to use for testing and provided a `TRUNCATE` command themselves
(executed by them, not by me) to get a clean slate — I did not run any
further destructive SQL against it directly.

## Notable decisions made along the way

- **EBITDA had to be computed, not searched for**: the real filing has no
  literal "EBITDA" line at all -- confirmed by dumping the actual
  extracted PDF text and checking. The pre-existing extractor was
  silently returning `None` (rendered as `€0`) for this document the
  whole time. Fixed by reconciling from `Group operating loss` +
  `Depreciation` (a cash-flow "Adjustments for:" line), the same
  reconciliation the filing's own cash flow statement performs.
- **Prior-period comparative capture, not calendar-aware multi-filing
  comparison**: the original plan assumed calendar-aware YoY would need
  multiple *uploaded* filings. But Senus's one filing is literally its
  first-ever public results (per the assignment brief) -- there will
  never be a second filing to diff against until one is actually
  published. Cross-checking the real PDF text found that almost every
  P&L/balance-sheet/cash-flow line already prints its own prior-year
  comparative in the same document, so the extractor captures that
  instead -- confirmed with the user before committing to this larger
  extractor change (see conversation: "Should the extractor capture the
  prior-year comparative column...").
- **`calculate_change` sign bug**: found by inspecting a live API response
  where ROCE improving from -156.7% to -75.9% displayed as "down" with a
  negative change. Fixed by dividing by `abs(previous)` -- the standard,
  well-known fix for percentage-change-of-a-negative-base, verified as a
  no-op for the existing all-positive metrics.
- **Cash runway from operating cash flow, not balance-sheet cash delta**:
  the balance sheet's cash increased overall (735,189 vs 72,382), but
  that's driven by a €1.1m equity raise (financing activity), not
  operating performance. Using the cash flow statement's "Net cash used
  in operating activities" line instead gives a real, undistorted burn
  rate.
- **Two `MetricsService` methods removed** (`calculate_margins`,
  `calculate_debt_ratios`) rather than left as unused dead code, per the
  expansion plan's own acceptance criterion -- `calculate_margins` is
  fully superseded by the extractor's own computation;
  `calculate_debt_ratios` had no caller and no planned one (interest_cover
  covers the Solvency KPI slot instead).

## Verification performed

- `cd backend && pytest tests/` -- 63 passed, including a dedicated
  regression test (`TestExtractAgainstRealFiling`) that runs the real
  extraction against the actual uploaded PDF, not just synthetic text.
- `cd frontend && npx vitest run` -- 64 passed; `npx tsc --noEmit` --
  no errors.
- Manually verified the database migration helper against the real,
  already-existing production `financial_metrics` table (confirmed via
  startup logs: "Adding missing column financial_metrics.revenue_prior"
  etc.), not just a fresh local database.
- Re-uploaded the real filing to a cleaned production database and
  confirmed `GET /metrics/dashboard/summary` end-to-end: correct values,
  correct signs/trend directions for every new ratio (including the
  negative-base cases the `calculate_change` fix addresses).
- **User visually confirmed the live dashboard** in their own browser
  (pointed at my local backend instance): all four new KPI cards
  present, correct values, correct colors/trend arrows, and sparklines
  now rendering on every KPI card (previously blank except revenue) since
  the embedded prior-period comparative gives every card a real 2-point
  series.
