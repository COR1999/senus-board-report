# AI Usage — feature/historical-trend-insight

## What was built

Part C of the plan that started with PR #56 (cadence-split trend chart) and PR #58 (persisted
per-report insights): a single AI-generated insight describing the *trajectory* across every report on
file, complementing AI Board Insights' per-report snapshot rather than replacing it.

### Backend

- New `HistoricalInsight` model (`backend/app/models/historical_insight.py`) — genuinely singleton
  (`insight: JSONB`, `data_fingerprint`, `model_version`, `generated_at`, no foreign key). Unlike
  `ReportInsights` (one row per report), there's exactly one "trend across all reports" for this
  single-user dashboard, so nothing natural to scope it by.
- `GET`/`PUT /metrics/dashboard/historical-insight` in `metrics.py`. Staleness detection: a new
  `_chart_data_fingerprint(points)` helper hashes the exact revenue-trend point set (SHA-256 of a
  canonical JSON serialization of `document_id`/revenue/EBITDA/cash/`cadence_months` per point,
  reusing `get_revenue_trend`'s own already-existing query by calling it directly rather than
  duplicating it). `GET` computes the current fingerprint and only returns the stored row if it
  matches; otherwise 404 (same "not yet" convention as `ReportInsights`, whether that means "never
  generated" or "generated but now stale"). `PUT` recomputes the fingerprint server-side too — never
  trusts a client-supplied one, so a stale/mismatched fingerprint can never be persisted as current.

### Frontend

- `lib/insights.ts`: `InsightType` gained `'trend'`; `parseInsightsResponse`'s allowed-type list
  extended to accept it. New `buildHistoricalInsightPrompt(chartData)` — buckets points into Full-Year
  (`cadence_months >= 9`) and Half-Year (`<= 6`) lists, describes each **separately**, and explicitly
  instructs Gemini never to imply a period-over-period change between the two — directly carrying PR
  #56's own "never blend two incomparable cadences into one line" principle into the prompt itself, so
  the AI-generated narrative can't describe a comparison the chart deliberately doesn't show. Asks for
  exactly 1 insight, always typed `"trend"`. New `FALLBACK_TREND_INSIGHT` (a single fallback item,
  distinct from the 3-item `FALLBACK_INSIGHTS` used for the report-scoped panel).
- `/api/insights/route.ts` now branches on the request body shape: `{ metrics }` (existing per-report
  flow) or `{ chartData }` (new trend flow) — kept on the same route rather than a second one
  specifically so both share the one Gemini circuit breaker/backoff state (same key/quota pool; a
  route split would need to duplicate and keep that state in sync).
- `data-service.ts`: `getHistoricalTrendInsight(chartData)` (live generation via `/api/insights`),
  `getStoredHistoricalInsight()` (404 → `null`, same "expected absence" convention as
  `getStoredInsights`), `saveHistoricalInsight(insight, modelVersion)` (PUT, upsert).
- New `HistoricalTrendInsight` component — its own distinct card next to `AiInsights` (a 2-column-ish
  grid in `dashboard-container.tsx`, `AiInsights` taking 2/3 width), not folded into the same insight
  list: the two answer different questions ("what does this one report say" vs. "what's the trajectory
  over time"). Renders nothing at all (`null`) with fewer than 2 real chart points — nothing meaningful
  to describe as a trend yet. Flow mirrors `AiInsights`' persisted-insights pattern: check stored first,
  fall back to live generation + persist (only non-fallback results), no per-report `reportId` needed
  since this insight isn't scoped to one.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5), completing the plan-then-implement-then-verify sequence
started with PR #56. No new design decisions needed mid-build beyond the standard pre-merge PR
confirmation — this was the last of three pre-agreed parts (A/B/C).

## Notable decisions made along the way

- **Fingerprint over a simple "regenerate on every load" or a manual refresh-only approach** — matches
  the exact "regenerate only when the underlying data actually changed" principle PR #58 established
  for per-report insights, applied to the whole-history case instead of one report.
- **Server-computed fingerprint, never client-supplied** — a client-trusted fingerprint could be
  (accidentally or not) mismatched from reality; computing it server-side on both `GET` and `PUT` makes
  that impossible by construction.
- **One route branching on body shape, not two routes** — the alternative (a dedicated
  `/api/historical-insight` route) would need its own copy of the rate-limit/billing circuit breaker,
  another piece of module-level state to keep in sync with the existing one for no real benefit, since
  both modes share the same underlying Gemini key and quota pool.
- **A distinct card, not folded into AI Board Insights' own list** — considered mixing a 4th "trend"
  item into the existing 3-insight panel, rejected: the two are genuinely different analyses (one
  report's snapshot vs. the whole history), and blending them into one undifferentiated list would
  blur that distinction rather than clarify it.

## A real bug found during verification

Adding `backend/tests/test_historical_insight.py` (which creates `FinancialMetrics` rows via
`session.add()`+`flush()`, the existing test-fixture convention in this codebase, then exercises the new
`PUT` endpoint) broke 33 previously-passing tests in `test_revenue_trend.py`/`test_metrics_summary.py`
when run as part of the full suite — but passed cleanly in isolation. Root cause: `conftest.py`'s
per-test `async_session` fixture only calls `rollback()` at teardown, which cannot undo a change that was
already `commit()`ted — and the new `PUT` endpoint's `db.commit()` (a correct, necessary call, matching
every other mutating endpoint in this project) committed not just its own change but every other pending
flushed row in that same session, including the test's own fixture data. Since the test suite's SQLite
database is a single session-scoped in-memory instance (`StaticPool`), that committed data then leaked
into every test file that ran afterward, corrupting `test_revenue_trend.py`'s exact-count assertions with
extra, unrelated rows. Fixed with an explicit `autouse` cleanup fixture in the new test file that deletes
everything it added after each test runs, restoring isolation regardless of which endpoint under test
happens to commit. This is a real, generalizable gap in the test harness itself (any test combining a
`flush()`-only fixture with a commit-triggering endpoint is exposed to it) — noted in `docs/roadmap.md`
rather than silently patched over.

## Verification performed

- `cd backend && python -m pytest tests/ -q` — 232 passed (228 pre-existing + 4 new
  `test_historical_insight.py` cases: 404 on nothing generated, create-then-read-back, 404-again once a
  new report changes the underlying data/fingerprint, upsert-replaces-not-appends).
- `cd frontend && npx vitest run` — 190 passed (179 pre-existing + 11 new: `buildHistoricalInsightPrompt`
  cadence-separation/warning/exactly-1/empty-cadence cases, `parseInsightsResponse` accepting `'trend'`,
  and `HistoricalTrendInsight` component tests covering the fewer-than-2-points empty state, rendering a
  stored result with zero live calls, falling back to live generation + persisting it, and never
  persisting fallback content).
- `cd frontend && npx tsc --noEmit` — no errors.
- `cd frontend && npx next build` — succeeds.
