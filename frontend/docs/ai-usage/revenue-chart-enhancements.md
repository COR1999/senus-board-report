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

## Round 2 — a second stakeholder's feedback ("David")

A different real reviewer gave four more notes on the same dashboard:

1. **"Visuals fall a bit flat... for one year of data, percentage comparison
   or bar chart is easier on the eyes than a line graph."** Investigated via a
   standalone comparison mockup (published as a Claude Artifact, not committed
   to the repo) showing the real 2-point data as both a line/area chart and a
   bar chart, plus a clearly-labeled *illustrative-only* mockup with fabricated
   placeholder periods through "Dec 2028" to show what a longer real time
   series would look like. User's decision after reviewing: **keep line/area**
   for the Revenue Trend chart — no code change from this specific note.
   Follow-up: asked whether any *other* chart in the app should be a bar
   instead. The only other chart is `KpiSparkline` (the tiny inline trend line
   on hero KPI cards) — recommended keeping it as a line too, since it's
   purely decorative context beside an already-explicit numeric delta+arrow,
   not a standalone comparison surface the way the main chart is.
2. **"For Bookings, remove the percentage thingy."** Real issue: Bookings has
   no prior-period comparative at all (its `history` is a single point), so
   its `changePercentage` was always a hardcoded `0`, and the stat strip
   showed a "0%" pill that read as a real (if flat) delta rather than "no
   comparison exists." Fixed generally, not by special-casing "bookings": the
   delta pill now only renders when `history.length >= 2`, i.e. a real prior
   value actually exists. This also protects any future stat-strip metric with
   the same no-prior-comparative shape.
3. **"Maybe put the AI executive insights up the top."** Before making this
   change, verified there's no staleness risk: `AiInsights`'s `useEffect` is
   keyed on the `metrics` prop, and `/api/insights` has no caching layer of
   its own -- it re-derives the OpenAI prompt from whatever `metrics` currently
   holds on every call. So a new report -> new `/metrics/dashboard/summary`
   response -> new `metrics` object -> a genuinely fresh AI commentary call,
   not a stale/cached one. (Aside, not a blocker: if OpenAI errors, the panel
   falls back to a hardcoded `FALLBACK_INSIGHTS` array with made-up numbers
   like "38% YoY" that don't match Senus's real figures -- worth knowing.)
   Moved `<AiInsights>` from beside the chart (bottom of page) to directly
   under the hero KPI row, full-width, ahead of the secondary stat strip and
   the chart.
4. **"Do you have net revenue retention figures -- are customers spending more
   than last year?"** Checked directly against the real filing text: the only
   customer count anywhere ("138 customer accounts") is a restated FY2025
   admission-document figure, not an HY2026-specific count, and there is no
   per-customer or cohort revenue breakdown, no "existing vs. new customer"
   split, anywhere in the text. NRR is not derivable from what this filing
   actually contains -- reported this as a hard data gap, not built.

## Verification performed

- `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q` — 94 passed.
- `cd frontend && npx vitest run` — 102 passed (re-ran after each round of polish: axis/tooltip, then bookings-badge/layout).
- `cd frontend && npx tsc --noEmit` — no errors (re-ran after each round, still clean).
- `cd frontend && npx next build` — succeeds (re-ran after each round, still succeeds).
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
