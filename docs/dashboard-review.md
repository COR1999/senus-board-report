# Executive Dashboard Review (2026-07-09)

> A product/design review of the Executive Dashboard (`/`), conducted by inspecting the actual
> source (frontend components, backend metrics/extraction services, data models) and live
> screenshots of the deployed app — not assumptions. Written before any of its recommendations
> were implemented; see `docs/roadmap.md` for the branches that executed it and what changed
> along the way.

## The verdict, up front

The backend in this project is genuinely disciplined: missing values are `null`, never a
fabricated zero; extraction confidence is scored and gated; mixed reporting cadences (a 6-month
filing next to a 12-month one) are kept from being blended into a fabricated trend at three
separate layers (KPI comparison, revenue trend, AI prompts). That discipline is worth preserving
exactly as-is. The problem was never data integrity — it's that the dashboard tried to present a
complete, always-full boardroom layout on top of a company that, at review time, had exactly two
real reporting periods on file, of two different cadences. Every layout decision downstream
inherited that mismatch.

### The one bug that explains the rest

The Revenue Trend chart is architected to split by cadence into two lines — a Full-Year line and
a Half-Year line (`frontend/components/dashboard/revenue-chart.tsx`, `buildChartRows`). That's the
right call in principle: it stops a 12-month total and a 6-month total from being drawn as if they
were sequential, comparable points, a real incident this codebase already fixed twice (see
`docs/roadmap.md`, the mixed-cadence entries). But with only two real filings on file — one FY, one
HY — each line had exactly one point. There was no line to draw. The chart rendered as two isolated
dots wearing a legend, gridlines, a metric switcher, and a forecast toggle that produced nothing
(`projectSeries` requires ≥2 known points per series, `frontend/lib/forecast.ts`) because neither
cadence bucket cleared that bar. This was the concrete case of "a chart that doesn't communicate
anything" — and it wasn't a rendering bug, it was the correct architecture applied to a data volume
it wasn't designed for.

The fix wasn't a rewrite. It was teaching the existing, well-built data-shaping logic
(`buildChartRows`) to choose a presentation appropriate to how many points it actually has — a
gauge for one, a bar comparison for two, a line only at three or more — instead of always reaching
for the line chart. The same "adapt to what's actually there" principle applies to the KPI grid,
the stat strip, and the forecast.

## Section-by-section audit (as the page rendered at review time)

- **Header** (title, "as of" date, period selector) — no notes. The period selector only renders
  with 2+ eligible periods, a good adaptive precedent worth reusing everywhere else.
- **Hero row** (Revenue, EBITDA, Cash, Customers) — right metrics, right size, right position. No
  fallback existed for a metric that couldn't be filled (e.g. EBITDA is `null` for the FY2025
  Information Document).
- **AI Board Insights + Historical Trend** — two cards immediately under the hero row, before any
  chart. Front-loaded narrative ahead of the evidence it was commenting on.
- **Stat strip** (Bookings, EBITDA Margin, Cash Runway, Interest Cover, ROCE) — confirmed via a live
  screenshot: selecting "FY2025" rendered all five as simultaneously empty. The Information
  Document (that period's source filing) is a single summary table with no cost breakdown, interest
  expense, or capital-employed figure, so none of the five could ever be computed for that period —
  not intermittently, structurally.
- **Revenue Trend chart** — see above.
- **Reports table** (full width, bottom of dashboard) — the same searchable/filterable/exportable
  component the dedicated `/reports` page renders. The right amount of chrome for a reports page,
  too much for the last section of an at-a-glance executive view.
- **Sidebar/navigation** — no notes; already matched the brief (icon rail, hover-expand, no nested
  menus, single presenter identity).

## Widget decisions

| Widget | Verdict | Reasoning |
|---|---|---|
| Hero KPI row (4 cards) | Keep | Right size/count/position; made data-driven so a missing metric swaps to a fallback instead of rendering empty. |
| 5-card stat strip | Redesign | Collapsed to an adaptive row using a fallback cascade instead of five fixed slots that could go empty together. |
| Revenue Trend chart | Redesign | Kept `buildChartRows`'s cadence-safety logic; added point-count-aware rendering (gauge / bar-pair / line). |
| "Show forecast" toggle | Redesign | Gated by real point count; falls back to guidance-based forecasting when trend data is thin. |
| AI Board Insights | Keep, relocate | Genuinely good machinery (persisted per-report, quota-guarded, category-tagged). Moved to the bottom; ranked by severity instead of a fixed 1-positive/1-risk/1-opportunity split. |
| Historical Trend Insight (separate card) | Merge | Folded into the same ranked insights feed using the already-defined `trend` badge style that was previously dead code. |
| Reports table on the dashboard | Cut down | Replaced with a plain "Recent Reports" list (a few rows, no search/filter/export chrome) linking to `/reports`. |
| Revenue/EBITDA/Cash metric switcher | Keep | Correct pattern — single y-axis, one series at a time, not a dual-axis overlay. |
| Waterfall (Revenue → Costs → EBITDA) | Add, conditionally | Real fields exist (`cost_of_sales`, `administrative_expenses`, `operating_result`) but only for documents with a full balance-sheet extraction; shown only when the selected period has them. |
| Segment/geography pie chart | Stay cut | Already correctly removed once the team confirmed Senus's filings have no structured segment split — no real data to plot. |

## The adaptive-data framework

Never show an empty widget, never fabricate a number — hide and substitute instead. The backend
already had the harder half of this solved (every missing field really is `null`). What was missing
was a selection layer that reads those nulls and picks a different, real metric instead of
rendering the gap.

| Category slot | Primary | Fallback 1 | Fallback 2 | If none resolve |
|---|---|---|---|---|
| Profitability | EBITDA Margin | Operating Margin | Gross Margin | Omit slot |
| Cash & Liquidity | Cash Runway | Net Cash Movement (`cash − cash_prior`) | — | Omit slot |
| Solvency & Leverage | Interest Cover | EBITDA Margin | Operating Margin | Omit slot |
| Returns | ROCE | Revenue per Customer (`revenue ÷ customers`) | — | Omit slot (rare) |
| Growth & Revenue | Bookings | Revenue Growth % | — | Omit slot |

Note the deliberate deviation from a naive rule set: "Bookings unavailable → show Customer Growth"
assumes a prior-period customer count to diff against, but the schema has no `customers_prior`
column (`financial_metrics.py`) — deliberately, since the one narrative customer count in a filing
is a fixed FY reference, not a period-over-period comparative pair. Building "Customer Growth" would
mean fabricating a number this project has otherwise been disciplined about never fabricating.
Falls back to Revenue Growth % (already real and computed) instead. A real Customer Growth metric
remains a legitimate follow-up if a filing is ever found to state a genuine prior customer count.

This is a frontend-only concern — every field the cascade needs was already exposed as
`null`-or-real on `DashboardSummaryResponse`; no backend change was required. It lives as a pure,
independently-testable function: `frontend/lib/kpi-selection.ts`.

## Chart selection

Render mode follows point count, per cadence bucket, not habit:

- **0 points** — bucket doesn't render at all (already true by construction).
- **1 point** — a single stat callout, not a chart.
- **2 points** — side-by-side bars, current period next to prior, both labelled with their real
  periods.
- **3+ points** — the existing area/line treatment, unchanged.

**Waterfall** (Revenue → Costs → EBITDA): Revenue → `− cost_of_sales` → Gross Profit →
`− administrative_expenses` → Operating Result (EBIT) → `+ D&A` → EBITDA, using real
`BalanceSheetMetrics` fields. No R&D line exists in the source filings, so a generic "Operating
Costs" bucket is used rather than inventing one. Hidden entirely for a period whose source filing
never had this level of detail.

**Pie charts**: no real segment, product-line, or geography split exists in any ingested filing —
stays cut.

## Forecast, redesigned

Two methods, chosen automatically by what the data can support:

- **Method One — historical trend** (existing `projectSeries`, unchanged logic): only offered for a
  cadence bucket with **3 or more real points**.
- **Method Two — management guidance** (new): Senus has stated a public growth target of a minimum
  50% CAGR through 2030. Where trend data is too thin for Method One, revenue is projected forward
  from the latest real figure at that stated rate instead of showing nothing —
  `projectFromGuidance(baseRevenue, baseYear, cagr, targetYear)` in `lib/forecast.ts`. The exact
  wording/base year/target year should be (and was) confirmed against the source filing text before
  shipping, the same sourcing discipline `financial_metrics_extractor.py` already applies to every
  regex it trusts.

Forecast cards proposed alongside the chart: Projected Revenue 2030, Expected CAGR, Growth
Multiple, Progress to Target. Illustrative example at review time (base FY2025 revenue €837K,
50%/yr to FY2030): ≈€6.4M projected 2030 revenue, 7.6× growth multiple, ~13% progress to target.

UI: keep the existing solid/dashed, full-opacity/reduced-opacity, indigo-for-projected treatment; add
a small "Trend-based" / "Guidance-based" method badge on the forecast segment, and a tooltip citing
the methodology (e.g. "Forecast based on published Senus 2030 strategy (minimum 50% CAGR).").

## Proposed page structure

Six sections, each answering exactly one of: are we growing, are we profitable, are we running out
of cash, what changed, what risks exist, what should management do next.

1. **Executive Summary** — hero KPI row (adaptive slot count, 4–6 cards).
2. **Financial Performance** — Revenue/EBITDA/Cash trend (gauge, bars, or line by point count) +
   cost waterfall when available.
3. **Financial Health** — margin/runway/returns ratios as gauges or progress components, adaptive
   cascade per category.
4. **Growth & Forecast** — the forecast chart (trend or guidance-based) + 2030 target cards.
5. **AI Executive Commentary** — ranked insights (3–6: risk → cash → profitability → growth →
   customers → operations → opportunity), each with a title, category, evidence, and
   recommendation. Includes the historical-trend narrative as one ranked entry rather than a
   separate card.
6. **Recent Reports** — a short pointer list (a few rows, no chrome) linking to the full `/reports`
   page.

This ordering mirrors how a board pack is actually read: the number, then what's behind the
number, then whether the balance sheet supports it, then where it's headed, then what a human
makes of all that. AI commentary moved from the second section to the close, turning it into a
synthesis of everything above it rather than a preview of it.

## Code notes

- This was a frontend-recomposition job, not a backend rewrite — every field the adaptive cascade
  needed was already `null`-or-real on `DashboardSummaryResponse`.
- New pure functions, tested independent of React/Recharts, following the pattern `buildChartRows`
  already set: `lib/kpi-selection.ts` (the fallback cascade), `lib/chart-render-mode.ts`
  (point-count → render mode), and an extension to `lib/forecast.ts` (`projectFromGuidance`).
- `dashboard-container.tsx`'s hardcoded `heroMetricConfig`/`statStripSource` arrays became derived
  data once `kpi-selection.ts` existed.
- No changes were needed to `metrics_service.py` or `metrics.py`'s confidence/cadence logic — it was
  already built exactly the way this review asked the frontend to behave.

## See also

- `docs/architecture.md` — "Dashboard composition" section documents the fallback-cascade rule as a
  designed behavior.
- `frontend/AGENTS.md` — "Layout patterns" section documents the point-count-driven chart render
  mode.
- `README.md`'s "Architecture decisions" table — includes the forecast method selection (trend vs.
  guidance) row.
- `docs/roadmap.md` — the branches that implemented this review's recommendations, in the order they
  actually shipped.
