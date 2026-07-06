# AI Usage — feature/revenue-analytics

## What was built

- Backend: new `GET /metrics/dashboard/revenue-trend` endpoint returning
  revenue by period (oldest -> newest) from the last 24 `FinancialMetrics`
  rows, for the revenue chart and forecast toggle.
- Frontend: `RevenueChart` now fetches real trend data (was mock-only) and
  adds a forecast toggle that projects the next 3 periods via linear
  regression (`lib/forecast.ts`) over known points. Added `SegmentBreakdown`
  (revenue by Government/Corporate/Agriculture) -- mock data only, since
  there is no backend extraction for customer segments.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). Given the
user's usage constraints this session, planning was lighter-weight than
`feature/kpi-system`'s full plan-mode process: direct codebase reads instead
of research sub-agents, and two targeted scope questions (segment data
source, revenue-trend backend-vs-mock) asked up front rather than a written
plan reviewed step by step. The user made both scope calls before
implementation began.

## Notable decisions made along the way

- **Segment breakdown has zero backing data anywhere in the backend** --
  not a UI gap, a data-model gap, same category as the Channels/Bookings
  narrative-extraction work already flagged as out-of-scope future work in
  `backend/docs/metrics-expansion-plan.md`. Confirmed with the user before
  building rather than assuming; built against mock data by their choice.
- **`ChartDataPoint.month` renamed to `period`**: the real source filing is
  a half-year report, not monthly, so a field literally named `month` was
  misleading once real data was wired in. Small, in-scope rename since it's
  core to what this branch touches.
- **Forecast is a visual projection, not a financial model**: plain OLS
  linear regression over known (non-null) points, explicitly documented as
  such in `lib/forecast.ts` so nobody mistakes it for a real forecasting
  model later.
- **New categorical palette for segment breakdown**: consulted the
  repo's `dataviz` skill before choosing colors (this is a genuinely new
  color decision, unlike kpi-system's sparklines which reused the
  already-established trend palette). Ran the skill's validator script
  against the 3-color candidate palette (blue/aqua/yellow, both light and
  dark surface) -- passed CVD separation, but light mode flagged a
  sub-3:1 contrast WARN on two colors, so direct text labels were added
  alongside the chart rather than relying on color/legend alone.
- **Missing-vs-zero convention carried forward**: `revenue-trend`'s
  `revenue` field is `Optional[float]`/`null`, matching the convention
  established (and cross-checked against `metrics-expansion-plan.md`) in
  `feature/kpi-system`.
- **Reapplied the `StaticPool` test-DB fix**: this branch was cut from
  `main`, which still has the `NullPool`-with-in-memory-SQLite bug fixed in
  `feature/kpi-system`. Reapplied here since the new revenue-trend tests
  need working `async_client`/`async_session` fixtures; the two branches
  will need reconciling on merge (same fix, applied independently).

## Verification performed

- `cd backend && pytest tests/` -- 14 passed.
- `cd frontend && npx vitest run` -- 18 passed.
- `cd frontend && npx tsc --noEmit` -- no type errors.
- Manually started the backend and hit `/metrics/dashboard/revenue-trend`
  directly against the real `senus.db` -- confirmed a correctly labeled,
  correctly valued single point for the one real uploaded document.
- No browser/screenshot tooling was available in this session, so the
  chart/toggle/segment-breakdown's actual visual rendering wasn't confirmed
  in a live browser -- covered instead by component-level tests (forecast
  toggle doesn't crash on click, segment labels render, chart renders with
  data).

## Known follow-up (not fixed here, out of scope)

- Both this branch and `feature/kpi-system` independently reapplied the
  same `conftest.py` `StaticPool` fix from diverged branch points --
  whichever merges second will hit a trivial conflict on that one line.
