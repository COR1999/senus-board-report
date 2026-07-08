# AI Usage — feature/persisted-ai-board-insights

## What was built

Part B of the plan that started with PR #56/#57 (the cadence-split revenue trend chart): AI Board
Insights previously only ever cached in `localStorage`, keyed by a hash of the current metrics content.
That survives a hard reload, but not a different browser/device, a cleared browser, or a genuine need to
look back at "what did the AI say about this specific report" later — for a genuinely single-user tool
whose underlying report data changes at most a few times a year, a report that already got a real
Gemini analysis should never need a second one just because local storage didn't carry it.

### Backend

- New `ReportInsights` model (`backend/app/models/report_insights.py`): `report_id` (unique FK to
  `reports.id`, `ondelete="CASCADE"`), `insights: JSON` (mirrors the frontend's own `Insight` shape —
  text/type/action/category), `model_version`, `generated_at`. One row per **report**, not per document
  — a regenerated report is a genuinely new analysis of possibly-different data, so it gets its own
  insights rather than inheriting the prior report's. A brand-new table needs no
  `_COLUMNS_ADDED_AFTER_INITIAL_RELEASE` migration entry — `Base.metadata.create_all` handles it on
  startup like every other table, once registered in `app/models/__init__.py`.
- `GET /api/reports/{report_id}/insights` — 404 when nothing's ever been generated for that report (an
  expected "not yet" state the frontend treats as a signal to generate, not an error).
- `PUT /api/reports/{report_id}/insights` — upsert (create or replace the existing row, never append a
  second one). The Gemini call itself stays entirely frontend-side, unchanged — this endpoint only ever
  *persists* what the frontend's own `/api/insights` route (`GEMINI_INSIGHTS_API_KEY`) already
  generated, keeping the two Gemini integrations' quota pools exactly as separate as this project's docs
  insist they must stay everywhere else.
- New `StoredInsight`/`ReportInsightsUpsert`/`ReportInsightsResponse` schemas in
  `backend/app/schemas/report.py` (insights are report-scoped, so they live alongside the existing
  report schemas rather than the financial-metrics ones).

### Frontend

- `data-service.ts`: `getStoredInsights(reportId)` resolves to `null` on a 404 (not a thrown error —
  matches the "expected absence, not a failure" convention this project already uses elsewhere) and
  `saveInsights(reportId, insights, modelVersion)` (PUT, throws on real failure like every other
  mutation call in this file).
- `/api/insights/route.ts` now also returns which Gemini `model` actually produced a real result (was
  previously only `{ insights, isFallback }`) — needed so a saved row records what generated it, not
  just the insights themselves.
- `ai-insights.tsx` flow rewritten: on load, `getStoredInsights(reportId)` first. If present, render it
  directly — **no Gemini call at all**. If absent (or `reportId` is `null`, e.g. the empty-dashboard
  state), fall back to the existing live `getAiInsights` flow, then `saveInsights(...)` the result —
  but only when it's a real, non-fallback generation, same reasoning PR #55 already established for the
  old cache (a quota-exhausted fallback must never look like "already handled" and permanently block a
  future retry). The manual refresh button's gate changed from a metrics-content-hash comparison
  (`hasCachedInsightsFor`) to "does a stored row exist right now for this report" (`hasStored` state) —
  a stronger key: it ties to *this specific extraction*, not "these particular numbers happened to
  repeat," which was always a slightly indirect proxy for the same intent.
- `dashboard-container.tsx`: resolves the `Report.id` to pass down by matching `metrics.document_id`
  (the backend's own resolved anchor — correct both in the default "latest" case and when a period is
  explicitly selected) against the reports list it already fetches for the Reports Table. `null` when
  nothing matches (the empty-dashboard state) — `AiInsights` still works in that case, generating live
  without ever calling the stored-insights endpoints, it just has nothing to persist against yet.
- `lib/insights-cache.ts` and its test file deleted outright — superseded entirely by backend
  persistence rather than kept running alongside it, removing the "lost on browser clear" caveat the
  localStorage version always carried.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5), continuing the same plan-then-implement-then-verify
discipline as every prior branch. This branch's scope (persist insights server-side, per report) was
already agreed as "Part B" of a larger plan before implementation started; no new design decisions
needed user input mid-build beyond the standard pre-merge PR confirmation.

## Notable decisions made along the way

- **Keyed by `report_id`, not document_id or a metrics hash** — a report is the actual unit of analysis
  ("what did the AI say about *this* extraction"), and unlike a metrics-content hash, it survives even
  if two reports happened to produce byte-identical KPI values.
- **Fallback content is never persisted** — directly reapplying the exact lesson from PR #55's
  `isFallback` fix to the new persistence layer, not just the old cache: saving a quota-exhausted
  placeholder would permanently block a future real generation for that report.
- **Branched off `main`, not stacked on the still-open PR #56/#57** — per this project's "one branch,
  one concern" discipline. Required a rebase once #57 merged mid-branch, to pick up its own (unrelated)
  addition of `Metrics.document_id` to the frontend type rather than silently duplicating that fix.
- **Deleted `insights-cache.ts` outright rather than leaving it as unused dead code** — this project's
  standing instruction to delete code confidently known to be unused rather than leave a "just in case"
  remnant.

## Verification performed

- `cd backend && python -m pytest tests/ -q` — 228 passed (222 pre-existing + 6 new
  `test_report_insights.py` cases: 404 on nothing-stored, 404 on a nonexistent report for both GET and
  PUT, create, read-back, and upsert-replaces-not-appends).
- `cd frontend && npx vitest run` — 179 passed. `ai-insights.test.tsx` fully rewritten for the new flow:
  renders a stored result with zero live Gemini calls, falls back to live generation and persists it,
  never persists fallback content, generates live with no persistence calls at all when `reportId` is
  `null`, disables refresh once a stored result exists (with the explanatory tooltip), and confirms
  refresh stays enabled and triggers a real second generation after an initial fallback result.
- `cd frontend && npx tsc --noEmit` — no errors.
- `cd frontend && npx next build` — succeeds.
