# AI Usage — feature/document-report-actions

## What was built

Pure frontend wiring for two backend endpoints that already existed:

- `deleteDocument()` / delete button on `/documents` (confirmation via
  `window.confirm`, since deleting cascades to the document's
  FinancialMetrics/BalanceSheetMetrics/Report rows).
- `regenerateReport()` / regenerate button on `ReportsTable`, used from
  both the dashboard's embedded table and the dedicated `/reports` page,
  via a new `onRegenerated` callback prop so each page controls its own
  refresh rather than `ReportsTable` owning that state.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). No new
backend work was needed -- both endpoints were already documented and
implemented.

## Notable decisions made along the way

- **`window.confirm` over a new dialog component**: no modal/alert-dialog
  primitive exists yet in `components/ui`; building one for a single
  destructive-action confirmation was more than this branch's scope
  needed.
- **`onRegenerated` callback rather than `ReportsTable` managing its own
  fetch**: `ReportsTable` is used in two places with different data-fetching
  patterns (`dashboard-container.tsx`'s bundled `Promise.all`, and
  `/reports/page.tsx`'s standalone fetch) -- a callback keeps the
  component reusable without assuming how its parent gets its data.
- **Found and fixed a test-isolation bug**: `vitest.config.ts` has no
  `clearMocks`, so spy call history leaks across tests in the same file --
  a "confirm cancelled -> delete not called" test failed because a prior
  test's successful delete call was still counted. Fixed locally via
  `vi.restoreAllMocks()` in this file's `beforeEach` rather than changing
  the shared vitest config, since auditing every other test file for
  reliance on the current behavior was out of scope for this branch.

## Verification performed

- `cd frontend && npx vitest run` -- 68 passed.
- `cd frontend && npx tsc --noEmit` -- no errors.
- Did not get to a full live-browser manual verification pass for this
  branch specifically before an unrelated, higher-priority production CORS
  bug came up mid-session (real deployed frontend blocked entirely from
  reaching the real deployed backend) -- pivoted to fix that immediately
  since it was actively blocking the user's live app.
