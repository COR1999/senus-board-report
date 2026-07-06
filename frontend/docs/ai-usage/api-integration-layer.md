# AI Usage — feature/api-integration-layer

## What was built

Introduces the reusable API/data-access layer named on the roadmap, without
changing any backend contract or existing `data-service.ts` function
signature:

- `lib/data-service.ts`: extracted a shared `apiFetch<T>()` helper so the ~10
  GET/POST functions stop each re-deriving their own fetch/headers/`res.ok`
  boilerplate. Behavior (typed responses, mock-data fallback on GET failures,
  throw-on-failure for mutations) is unchanged — this is a pure
  de-duplication, not a rewrite.
- `lib/hooks/use-async-data.ts`: a generic `useAsyncData<T>(fetcher, deps)`
  hook returning `{ data, loading, error, refetch }`. `data` starts `null`
  (not a fabricated empty array/object) so "still loading" is distinguishable
  from "loaded, genuinely empty".
- `lib/hooks/use-dashboard-data.ts`: thin typed wrappers — `useMetrics`,
  `useChartData`, `useSegments`, `useReports`, `useDocuments` — each just
  `useAsyncData` bound to the matching `data-service.ts` function.
- `lib/hooks/use-mutations.ts`: `useUploadDocument`, `useDeleteDocument`,
  `useRegenerateReport`. These wrap the existing throw-on-failure mutation
  functions and are the actual fix for a real gap: every mutation call site
  previously only did `console.error` on failure, so a failed upload/delete/
  regenerate was invisible to the user in the browser.
- `dashboard-container.tsx`, `app/reports/page.tsx`, `app/documents/page.tsx`,
  and `reports-table.tsx` now consume these hooks instead of hand-rolled
  `useState`/`useEffect` fetch logic, and all three pages now render a
  visible error banner when a fetch or mutation fails (previously: dashboard
  had a coarse all-or-nothing error message that could never actually fire in
  practice, since the underlying GET functions already catch and fall back to
  mock data internally; reports/documents pages had no error UI at all).

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5), following the
ground rules the user set for this branch specifically: typed API responses,
a reusable fetch layer, React hooks for data access, and handling loading/
error/empty states rather than hardcoding data.

## Notable decisions made along the way

- **`data: T | null`, not a fabricated empty default**: mirrors the same
  missing-vs-zero discipline already established for financial metrics
  (`history: (number | null)[]`, etc.) — a hook shouldn't invent a `[]` or
  `{}` that the caller can't tell apart from "the real data really is empty".
  Every call site already null-coalesces (`?? []`) at the render boundary
  where an empty list is genuinely fine to show.
- **`error` from the GET hooks will rarely fire today**: `getMetrics`,
  `getChartData`, `getReports`, `getDocuments`, `getSegmentBreakdown` all
  already catch their own network errors internally and resolve with mock/
  fallback data (a deliberate, pre-existing design so the dashboard never
  goes blank). `useAsyncData`'s `error` state exists for fetchers that do
  reject — which today means only the three mutation hooks — and for any
  future endpoint that's added without a fallback. This was verified
  directly: a rejected fetcher surfaces as a string error (test:
  `use-async-data.test.ts`), a resolved-with-fallback fetcher never does.
- **Loading-state reset lives in `refetch()`, not synchronously in the
  effect body**: an initial implementation called `setLoading(true)` /
  `setError(null)` as the first lines inside the `useEffect`, which
  `eslint-config-next`'s `react-hooks/set-state-in-effect` rule flags as a
  cascading-render risk (`next lint` failed on it). Fixed by moving that
  reset into the `refetch` callback itself (a plain event-handler-style
  function, not an effect body) — the initial mount's `loading: true` comes
  from `useState`'s initial value instead, so no reset is needed there.
  `npx eslint .` confirmed clean on every changed/new file afterward.
- **Didn't touch `ai-insights.tsx`**: it already has its own correct-enough
  fetch-on-prop-change pattern (keyed off the `metrics` prop, not a
  standalone endpoint call with its own loading/error toggle) and isn't one
  of the duplicated boilerplate call sites this branch targets.
- **Didn't add a generic mutation-error toast/snackbar system**: each
  page/table already had its own place to show an inline error banner
  (`DashboardShell`'s content area, `ReportsTable`'s card body); a global
  toast system wasn't asked for and would be new UI surface for a
  feature-scoped branch to introduce.

## Verification performed

- `cd frontend && npx vitest run` — 76 passed (69 existing + 7 new: 3 for
  `useAsyncData`'s loading/data/refetch/error behavior, 4 for the three
  mutation hooks surfacing a rejected call as a user-facing `error` instead
  of throwing).
- `npx tsc --noEmit` — no errors.
- `npx eslint .` — no new errors or warnings on any file this branch
  touched (2 pre-existing, unrelated issues remain in files this branch
  didn't touch: `sidebar.tsx`, `kpi-card.test.tsx`).
- `npx next build` — production build succeeds, all routes
  (`/`, `/reports`, `/documents`, `/settings`, `/api/insights`) compile.
- Existing `documents/__tests__/page.test.tsx` and
  `reports-table.test.tsx` (written for the pre-hooks implementation) still
  pass unmodified against the refactored components, confirming the public
  behavior (calls to `getDocuments`/`deleteDocument`/`regenerateReport`,
  confirm-before-delete, refetch-after-mutation) is unchanged.
- Real OpenAI call not verified end-to-end this session (this branch didn't
  touch the AI Insights integration).
- Visual check of the new error banners in a browser not available this
  session — happy to walk through it live if you open a localhost for me to
  test against, as with prior branches.
