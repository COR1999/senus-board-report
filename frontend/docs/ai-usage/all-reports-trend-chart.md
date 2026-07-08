# AI Usage — feature/all-reports-trend-chart

## What was built

Directly after PR #55, the user asked for the Revenue Trend chart to stop re-anchoring on whichever
reporting period is selected on the dashboard (`?document_id=`, truncating to that period's own
same-cadence history) and instead always show the whole real history, with the selected period
highlighted rather than filtered to.

The design conversation self-corrected once cadence came up: the first instinct (one continuous line
across every period regardless of cadence) would connect an HY (6-month) revenue figure to an FY
(12-month) figure on the same line — visually implying a comparable magnitude jump/drop that isn't
real, the same class of incident PR #43/#53 already guarded against for the KPI cards. Landed instead
on **two lines, split by cadence** (Full Year / Half Year), sharing one chronological x-axis, with each
line getting its own **independent forecast** — the concrete reason this beat a blended line or an
annualized-normalization approach: with both cadences' forecast tails merged into the same trailing
x-positions, a viewer can directly compare "is the Full-Year line actually tracking to what the
Half-Year run-rate implied."

### Backend

- `GET /metrics/dashboard/revenue-trend` (`backend/app/api/routes/metrics.py`) dropped its
  `document_id` query param, anchor resolution, and cadence-exclusion/truncation logic entirely — it
  now always returns every `_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` row, oldest → newest, capped at
  `REVENUE_TREND_WINDOW`. `get_dashboard_metrics` (the KPI cards) is untouched — only the trend chart's
  own endpoint changed.
- `RevenueTrendPoint` (`backend/app/schemas/financial.py`) gained `document_id: Optional[int]` and
  `cadence_months: Optional[int]` (reusing the already-existing `_cadence_months` helper) so the
  frontend can bucket and highlight without any further backend logic.
- The single-document synthetic-prior-point fallback (fewer than 2 real rows) is kept, now gated on the
  *total* result set rather than a truncated-to-anchor one.

### Frontend

- `ChartDataPoint` (`lib/data-service.ts`) gained the same two fields; `getChartData()` dropped its
  `documentId` param entirely (now always fetches the full history, decoupling the chart fetch from the
  period selector — switching periods triggers a KPI refetch, never a chart refetch).
- `RevenueChart` (`components/dashboard/revenue-chart.tsx`) rewritten to bucket `data` client-side via a
  new `cadenceBucket(cadenceMonths)` (`≤6` → Half Year, `≥9` → Full Year, undeterminable → an isolated
  "Other" marker with no connecting line — never guessed into either real series). Two `<Area>` series
  render with related-but-distinct colors per metric (e.g. Revenue: `#10b981` Full Year / `#6ee7b7` Half
  Year) — deliberately not the forecast overlay's dashed/indigo treatment, which stays uniquely "this is
  projected, not real." A new `selectedDocumentId` prop drives a custom Recharts dot renderer
  (`makeSeriesDot`) that draws a larger dot with a soft halo on whichever point matches the currently
  selected period, without filtering the rest of the chart out.
- Forecasting (`lib/forecast.ts`'s existing `projectSeries`) now runs twice — once per cadence's own
  historical points — and both tails are merged **by index** into the same trailing "Next Report N"
  rows, not appended as two separate trailing series. This index-aligned merge is what lets the
  Half-Year and Full-Year projected points land at the same x-position for direct visual comparison.
- `dashboard-container.tsx`: `useChartData()` no longer takes the selected period; `<RevenueChart>` gets
  `selectedDocumentId={metrics.document_id}` — deliberately the backend's own resolved anchor, not the
  raw `selectedDocumentId` component state (which stays `null` in the default "show latest" case and
  would never highlight anything).

### A real bug found while extending `Metrics`

`frontend/lib/data-service.ts`'s `Metrics` interface was missing a `document_id` field the backend's
`DashboardSummaryResponse` had already been returning since PR #44 (used to anchor "latest" on a
specific period) — nothing on the frontend had needed to read it until this branch. Added it, plus to
`mockMetrics` and every test fixture across `ai-insights.test.tsx`, `dashboard-container.test.tsx`, and
`insights.test.ts`.

### Making the new chart logic actually testable

The chart's `useMemo` bucketing/forecast-merge logic was extracted into a small, pure, exported
`buildChartRows(data, metric, showForecast)` function specifically so it has real, direct unit coverage.
This was a deliberate response to a real limitation found while writing tests: `ResponsiveContainer`
(Recharts) measures zero width under jsdom and never renders its actual SVG children — confirmed with a
throwaway probe test (`screen.debug()` + `container.querySelectorAll('circle').length === 0`) showing no
legend text and no dot elements at all in the rendered output, even with real two-cadence data passed
in. Rather than fighting jsdom with a fake `ResizeObserver`/mocked layout, the pure data-shaping step was
pulled out and tested directly — the same reasoning already used for `lib/forecast.ts`'s own
`projectSeries` being a standalone, component-independent function.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5), continuing the same plan-then-implement-then-verify
discipline as every prior branch this session. The cadence-split design itself (vs. one blended line)
was a real back-and-forth with the user — the initial one-line proposal was self-corrected once the
HY/FY magnitude-mismatch risk was raised, matching this project's standing "never let two different
reporting cadences visually blend into one implied trend" rule from PR #42/#43/#53.

## Notable decisions made along the way

- **Two lines by cadence, not one blended line or an annualized-normalization approach** — chosen
  specifically because it preserves every real reported number unchanged (no estimation/scaling) while
  still being visually honest about what's comparable to what.
- **Per-cadence forecasts merged by index, not appended separately** — the whole point of the
  design (comparing a Half-Year run-rate projection against where the Full-Year line's own point
  lands) only works if both tails share the same x-axis positions.
- **`selectedDocumentId` sourced from `metrics.document_id`, not the raw selector state** — caught and
  fixed before shipping: the raw `selectedDocumentId` React state defaults to `null` ("nothing
  explicitly picked"), which would leave the true-latest point unhighlighted by default; the backend's
  own resolved anchor is correct in both the default and explicitly-selected cases.
- **Pure-function extraction over fighting jsdom** — `ResponsiveContainer`'s zero-width behavior under
  jsdom is a known Recharts/jsdom limitation, not a bug in this codebase; extracting `buildChartRows`
  gives direct, fast, deterministic coverage of the actual logic worth testing, rather than an
  elaborate (and fragile) ResizeObserver mock just to coax Recharts into rendering real SVG in tests.

## Verification performed

- `cd backend && python -m pytest tests/ -q` — 222 passed.
- `cd frontend && npx vitest run` — 186 passed (176 pre-existing + 10 new: `cadenceBucket` cases,
  `buildChartRows` bucketing/forecast-merge/handoff cases, and a mixed-cadence-with-selection smoke
  test on the real component).
- `cd frontend && npx tsc --noEmit` — no errors (verified after each round of the `ChartDataPoint`
  interface-extension cascade across ~15 call sites).
- `cd frontend && npx next build` — succeeds.
