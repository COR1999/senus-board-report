# AI Usage — feature/kpi-system

## What was built

- Backend: `GET /metrics/dashboard/summary` now returns a typed
  `DashboardSummaryResponse` (was an untyped dict) with a new `history`
  array per KPI for sparklines, sourced from the last 8 `FinancialMetrics`
  rows. `change`/`trend` semantics (diff of latest two uploads) unchanged.
- Frontend: fixed `KpiCard`'s `trend` type to include `"neutral"` (previously
  only `"up" | "down"`, so a neutral trend silently rendered with "down"
  styling). Added `KpiSparkline`, `lib/format.ts` (trend -> style/color
  mapping), and `lib/metrics.ts` (general-purpose delta utilities).
- Cleanup: replaced `frontend/AGENTS.md` (previously only injected/fake
  content) with real project context; removed the stale `frontend/GEMINI.md`.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5) from a plan
reviewed and approved by the user beforehand. The user directed scope,
answered design questions (sparkline data source, backend vs. frontend-only),
and reviewed the plan before implementation began.

## Notable decisions made along the way

- **`HISTORY_WINDOW = 8`**: an arbitrary but reasonable default for how many
  past documents feed a sparkline; easy to tune later, not derived from a
  specific product requirement.
- **Missing-vs-zero convention**: an early draft of this plan coerced missing
  `FinancialMetrics` fields to `0.0` in the `history` array. Cross-checking
  `backend/docs/metrics-expansion-plan.md` (at the user's request) surfaced
  that this codebase already fixed a "missing-vs-zero" bug once and mandates
  `None`/`null` for missing data, never a fabricated `0`. The plan and
  implementation were corrected before any code was written, end-to-end
  (Pydantic `Optional[float]` -> TS `number | null` -> `KpiSparkline` drops
  nulls rather than plotting them).
- **Found and fixed an unrelated, pre-existing test bug**: `conftest.py`'s
  `async_client`/`async_session` fixtures used `NullPool` with an in-memory
  SQLite database, so each new connection got a fresh, empty database. No
  passing test exercised these fixtures before this branch. Switched to
  `StaticPool` (the pattern already proven in `test_integration.py`) so the
  new endpoint tests could actually run.
- **AGENTS.md/GEMINI.md cleanup**: while exploring, `frontend/AGENTS.md` was
  found to contain only an injected/fake instruction aimed at AI coding
  agents (not real project content), and since `frontend/CLAUDE.md` imports
  it directly, that content was loading into every Claude Code session in
  this repo. Flagged to the user, then replaced with real guidance at their
  request. `GEMINI.md` was deleted outright (Gemini isn't used in this
  frontend, only for backend financial-data analysis elsewhere).

## Verification performed

- `cd backend && pytest tests/` — 14 passed.
- `cd frontend && npx vitest run` — 31 passed.
- `cd frontend && npx tsc --noEmit` — no type errors.
- Manually started the backend and hit `/metrics/dashboard/summary` directly
  against the real `senus.db` (one existing uploaded document) — confirmed
  `history` returns correctly (`[354813.0]` for revenue, `trend: "neutral"`).
- No browser/screenshot tooling was available in this session, so the
  sparkline's actual visual rendering wasn't confirmed in a live browser --
  covered instead by component-level tests asserting sparkline presence/
  absence and neutral-trend styling.
