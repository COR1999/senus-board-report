# AI Usage — feature/dashboard-period-selector

## Context

Once the FY2025 Information Document was extracted (PR #42) alongside the existing HY2026 half-year
filing, the dashboard had no way to deliberately view either period — it always showed whichever was
extracted most recently. `docs/roadmap.md` had already scoped this as a real, not-yet-built idea
("A real reporting-period selector"); the user picked it directly as the next feature to build.

## What was built

- `GET /metrics/dashboard/periods` — lists every period eligible to reach the dashboard (same
  `_HAS_CORE_METRICS`/`_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` filters as "latest"), newest first, each
  labeled with the bare period + calendar range combined, e.g. `"FY2025 (Jul 2024 – Jun 2025)"`.
- `GET /metrics/dashboard/summary` and `GET /metrics/dashboard/revenue-trend` both gained an optional
  `?document_id=` param that anchors "latest" on a specific document instead of the true most recent
  one. Selecting an older period truncates to that period plus its own same-cadence history (nothing
  extracted after it) — the dashboard shows itself "as of" that period, consistent between the KPI
  cards and the trend chart. Omitting the param is unchanged default behavior, guarded by every
  pre-existing test for both endpoints passing unmodified.
- Frontend: a `Select` (reusing the exact shadcn/ui pattern already used for the Documents page's
  period filter) next to the existing "Data as of" banner, hidden when fewer than two periods exist.
  `useMetrics`/`useChartData` take a `documentId` param threaded into `useAsyncData`'s `deps` so
  switching periods triggers a refetch.

## A real bug found while testing

The "no eligible rows at all" empty-dashboard branch on `/dashboard/summary` returned `200` (the
generic empty state) instead of `404` for an explicit, nonexistent `document_id` — the empty-rows
check ran *before* the anchor-resolution logic, so a bad `document_id` against an otherwise-empty
table silently fell through to the wrong branch. Caught by a test seeding a single `needs_review` row
(making the eligible set empty) and requesting that row's own `document_id` — found before merge, not
in production. Fixed by checking `document_id is not None` inside the empty-rows branch and raising
`404` there, before falling through to the generic empty state.

## Verification performed

- `pytest tests/` — 177 passed (8 new: `/dashboard/periods` listing/filtering, anchored
  summary/trend against a real mixed-cadence fixture setup, 404s for nonexistent and ineligible
  `document_id`, and a regression test confirming default (no-param) behavior is unchanged).
- `npx vitest run` — 138 passed (7 new: fetcher query-string tests, Select rendering/hiding, and a
  test confirming selecting a period calls `getMetrics`/`getChartData` with the right `document_id`).
- `npx tsc --noEmit` and `npx next build` — both clean.
- **Real end-to-end verification, not just tests**: ingested both real fixtures (the half-year filing
  and the Information Document) through the actual upload pipeline (real PyMuPDF extraction, real
  `FinancialMetricsExtractor`, real confidence scoring — both scored 100%, `auto_accept`) against a
  throwaway local database, then called the new routes directly and via a real running HTTP server —
  confirmed the exact real production figures (HY2026: €355K revenue; FY2025: €837K revenue, +21.6%,
  correctly isolated from the HY row).
- **Real browser screenshot verification**: started a throwaway local backend + a `next build`/`next
  start` production frontend build (Next.js dev mode's Turbopack HMR websocket failed to establish in
  this sandboxed environment, which silently prevented client-side hydration — worked around by
  testing against a production build instead, which doesn't depend on the HMR socket), loaded the
  dashboard in headless Chromium via Playwright, and confirmed visually: the selector renders both
  real periods with correct combined labels and a checkmark on the active one; selecting "FY2025"
  updates every KPI card (revenue, EBITDA correctly N/A, cash, customers), the ratio stat strip
  (correctly all N/A — undisclosed by that document type), and the revenue trend chart, matching the
  real figures exactly.
