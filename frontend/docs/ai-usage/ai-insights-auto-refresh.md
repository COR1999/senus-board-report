# AI Usage — feature/ai-insights-auto-refresh

> **Note**: this branch was authored while the AI Board Insights panel still
> called OpenAI. `feature/gemini-ai-insights` (merged separately, afterwards)
> swapped that panel over to Gemini. The "OpenAI" mentions below are a
> historically accurate record of the provider *at the time this work was
> done*; nothing in this branch's actual code depends on which provider
> `getAiInsights` calls, so no functional changes were needed post-rebase --
> only two stray code comments (in `dashboard-container.tsx` and
> `use-async-data.ts`) were updated to say "Gemini" so they don't read as
> stale/wrong once merged.

## What was built

Two related requests in the same conversation:

1. "Can the AI board insight reload whenever we get a new report?"
2. Refined immediately after: "only call the AI insight whenever new
   reports have been uploaded and there is new data to analyze -- check my
   current structure so you don't have unnecessary [OpenAI] calling."

Both are satisfied by the same underlying fix, made once at the shared data
layer rather than inside `AiInsights` itself:

- **`lib/hooks/use-async-data.ts`**: `useAsyncData` gained an optional
  `pollIntervalMs`. When set, it re-fetches in the background on that
  interval -- but a poll that returns content identical to what's already
  held is compared by *value* (`JSON.stringify`), not object reference, and
  the old reference is kept rather than replaced. Background polls also
  never flip `loading` back to `true` (no repeating skeleton flash).
- **`lib/hooks/use-dashboard-data.ts`**: `useMetrics`/`useChartData`/
  `useReports`/`useDocuments` now accept and forward an options object
  (backward compatible -- every existing call site with no arguments is
  unaffected).
- **`dashboard-container.tsx`**: the three hooks it uses (`useMetrics`,
  `useChartData`, `useReports`) now pass `pollIntervalMs: 60_000`.

Why this satisfies request #2 without touching `AiInsights` at all:
`AiInsights`'s existing `useEffect(() => { getAiInsights(metrics) }, [metrics])`
already only re-runs when `metrics` is a *new* object reference. Since the
content-comparison fix means a background poll only ever produces a new
`metrics` reference when the fetched values actually changed, the OpenAI
call is now structurally only ever triggered by real new data -- not by
every 60-second poll tick, which was the real risk the user was flagging.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5). The fix location (the shared
`useAsyncData` hook, not `AiInsights` itself) was a deliberate choice after
reading the actual call chain (`AiInsights` <- `dashboard-container.tsx` <-
`useMetrics` <- `useAsyncData` <- `getMetrics`) rather than patching
`AiInsights` locally, since the same "don't create a new object for
unchanged data" guarantee is now available to any other polled hook, not
just this one case.

## Notable decisions made along the way

- **Content comparison via `JSON.stringify`, not a deep-equal library**:
  every value flowing through this hook is a plain JSON-serializable API
  response shape already (straight from `res.json()`), so this is sufficient
  without adding a dependency.
- **60-second interval**: this is a personal/board dashboard updated a
  handful of times a year, not a live trading terminal -- frequent enough to
  feel responsive without meaningfully increasing backend/OpenAI load.
- **Polling added to `useMetrics`/`useChartData`/`useReports` together, not
  just `useMetrics`**: a new report changes the chart and reports table too,
  not just the KPI summary -- polling only the metrics hook would have left
  the rest of the dashboard visibly stale next to fresh KPI cards.
- **Terminology correction**: the user referred to this as "Gemini calling"
  -- the AI Board Insights panel actually calls OpenAI (`app/api/insights/
  route.ts`); Gemini is a separate, backend-only service used during PDF
  extraction (see `AGENTS.md`: "these are independent integrations, don't
  conflate them"). Worth keeping straight since they have separate quotas/
  billing.
- **Found and fixed a pre-existing test-isolation bug while adding tests**:
  `ai-insights.test.tsx` had no `afterEach(vi.restoreAllMocks)`, so a spy's
  call count leaked across tests in the same file (same issue previously
  found in `feature/document-report-actions`) -- this only surfaced once a
  test asserted an exact call count, which none had before.

## Verification performed

- `cd frontend && npx vitest run lib/hooks/__tests__/use-async-data.test.ts`
  — 7 passed, including new fake-timer tests proving: polling re-invokes the
  fetcher on schedule, an unchanged poll result keeps the same object
  reference, a changed result replaces it, and `loading` never flips back
  to `true` on a background poll.
- `cd frontend && npx vitest run components/dashboard/__tests__/ai-insights.test.tsx`
  — passed, including a test proving `AiInsights` does not call
  `getAiInsights` again on a re-render with the same `metrics` reference
  (the polling-safety contract this branch depends on), reconciled after
  rebasing onto `main` with the data-driven refresh-gate tests added by
  `feature/gemini-ai-insights`.
- `cd frontend && npx vitest run` — full suite passes.
- `cd frontend && npx tsc --noEmit` — no errors.
- `cd frontend && npx next build` — succeeds.
- Confirmed the still-running local preview (dev server + throwaway SQLite
  backend from the code-quality session) survived being switched through
  three different git branches while live, and continued responding
  correctly on both the frontend (`:3010`) and backend (`:8030`) throughout.
