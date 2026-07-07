# AI Usage — feature/revenue-chart-enhancements

## What was built

Triggered by direct stakeholder feedback (a real board-level reviewer, "Dad",
live-testing the dashboard) on two points about the Revenue Trend chart:

1. **"Not clear if 6-month or 12-month data points, is HY2025 June 2025?"** —
   the axis only ever showed the filing's own "HY2026"/"HY25" labels, which
   don't say which calendar month the period actually ends (Senus's fiscal
   year runs Jul-Jun, so "HY2026" ends in December, not June — a reasonable
   reader could easily assume otherwise).
2. **"Is EBITDA really down when revenue is up?"** — not a bug: administrative
   expenses grew ~15.3% (€677.9k → €782.0k) while revenue grew only 4.1%
   (€340.9k → €354.8k), so the operating loss widened and EBITDA worsened
   despite top-line growth. Confirmed by re-deriving both numbers directly
   from the filing's own P&L lines. No code change needed for this one — it
   surfaced the value of a follow-up: letting a viewer actually see the
   EBITDA/Cash trend alongside Revenue on the same chart, which became the
   second half of this branch (matching an exploratory idea the user had
   floated earlier, see `project_chart_metrics_idea` in memory).

Changes:

- **Backend**: `FinancialMetricsExtractor` now extracts the filing's real
  period-end date from its own "for the six months ended 31 December 2025"
  text (`reporting_period_end` = "Dec 2025"), with the prior period derived
  as the same month one year earlier ("Dec 2024") — safe because half-year
  filings always compare like-for-like halves a year apart, never a guess.
  New nullable `reporting_period_end`/`reporting_period_end_prior` columns
  (additive migration via the existing `_add_missing_columns` mechanism, no
  Alembic in this project). `GET /metrics/dashboard/revenue-trend` now
  prefers this month label over the bare "HY" label, and returns `ebitda`/
  `cash` per point (both already existed as columns, just not exposed here).
- **Frontend**: `RevenueChart` gained a series-swap metric toggle
  (Revenue/EBITDA/Cash — one plotted at a time on a single y-axis, per the
  dataviz skill's "never dual-axis" rule, since the three are on very
  different scales and EBITDA is currently negative). `lib/forecast.ts`'s
  `projectRevenue` was generalized to `projectSeries(history, metric,
  periodsAhead)` so the linear-trendline forecast toggle works for whichever
  metric is selected, not just Revenue — floors at 0 only for Revenue
  (EBITDA/Cash can legitimately be negative or shrink).
- **Axis polish**: y-axis widened to 68px with `tickMargin` so a negative
  EBITDA label ("-€473.7K") never clips, same width kept across all three
  metrics so switching the toggle doesn't jitter the plot area; x-axis given
  breathing room via `tickMargin` too.
- **New `components/ui/tooltip.tsx`**: a small Radix-based hover tooltip
  (matching this repo's existing shadcn/Radix primitive pattern), added
  because none existed yet. Used for a new info icon next to the chart's
  period label explaining what "HY" means and that Senus's fiscal year runs
  Jul-Jun (so HY2026 ends in December) -- directly answering the
  stakeholder's ambiguity question inline, not just via the axis label.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5). The two stakeholder questions
were answered by re-deriving the numbers directly from the filing's own P&L
table (not asserted from memory), and the chart-toggle *design* (series-swap
vs. small multiples vs. indexed-to-100) was confirmed with the user before
building, since it was a genuinely open design choice recorded as
exploratory in a prior session.

## Notable decisions made along the way

- **Series-swap over small multiples or indexed-to-100**: user's explicit
  choice when asked, matching the dataviz-skill-safe pattern already
  recorded from an earlier session's open question.
- **Month-end label takes priority over the "HY" label, not a replacement**:
  `reporting_period`/`reporting_period_prior` ("HY2026") are left untouched
  everywhere else (KPI card subtitles still read "HY25 vs HY2026") — this
  branch only changes what the *chart axis* prefers, since that was the
  specific ambiguity raised.
- **Forecast generalized to all three metrics, not revenue-only**: initial
  implementation restricted forecasting to Revenue (2 real EBITDA/Cash points
  felt like weak grounds for a trendline) — reversed after the user asked
  directly for EBITDA/Cash forecasting too. Same trendline math, just keyed
  by metric now.
- **Prior-period end date derived, not extracted**: the filing states its
  own end date once ("ended 31 December 2025") but never states the prior
  period's end date as text — deriving it as the same month one year earlier
  is safe for this filing's cadence (confirmed against the real PDF, not
  just the synthetic test fixture).

## Verification performed

- `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q` — 94 passed.
- `cd frontend && npx vitest run` — 100 passed (re-ran after axis/tooltip polish, still 100).
- `cd frontend && npx tsc --noEmit` — no errors (re-ran after axis/tooltip polish, still clean).
- `cd frontend && npx next build` — succeeds (re-ran after axis/tooltip polish, still succeeds).
- Extraction re-verified directly against the real filing PDF (not just the
  synthetic test fixture): `reporting_period_end == "Dec 2025"`,
  `reporting_period_end_prior == "Dec 2024"`.
- End-to-end against the real production DB: ran the backend locally against
  the live Railway Postgres (existing project convention), the additive
  migration applied cleanly, regenerated the one existing report to backfill
  the new columns on the pre-existing `FinancialMetrics` row, then confirmed
  `GET /metrics/dashboard/revenue-trend` returns
  `[{"period":"Dec 2024","revenue":340931.0,"ebitda":-395561.0,"cash":72382.0},
  {"period":"Dec 2025","revenue":354813.0,"ebitda":-473739.0,"cash":735189.0}]`.
- Not yet deployed: the live Vercel frontend still points at the unmodified
  Railway backend, so EBITDA/Cash won't show on the deployed chart until this
  branch is merged and the backend redeployed.
