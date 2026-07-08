# AI Usage — feature/needs-review-approve-workflow

## Context

Importing the real ADF Farm Solutions filing (PR #48/#50) worked end-to-end but landed as
`needs_review` — a scanned document with no P&L text layer, so only cash and a customer count came
back via Gemini vision, 55% confidence. The Documents page already showed a "Pending Review" tag for
it, but the user's own words: *"but i have no way to review the document"*. There was a real gap: the
figures were extracted and persisted, but nothing on the frontend let a human actually look at them or
promote the document onto the dashboard.

## The design

The confidence gate's own score/tier (`extraction_confidence`/`extraction_confidence_tier`) is a
permanent, honest record of what the extractor actually found — rewriting it on approval would make it
lie about its own history. So approval is a **separate, independent field**:
`FinancialMetrics.human_approved_at` (a timestamp, not a bool, so "when" is preserved for free). Two
places read it:

- `metrics.py`'s `_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` — a `needs_review` row with `human_approved_at`
  set now counts as eligible for "latest", alongside the existing `>= 95` / `NULL` cases.
- `documents.py`'s new `_effective_tier(tier, human_approved_at)` helper — the tier as shown to API
  consumers reads as `auto_accept` (no more "Pending Review" tag anywhere) once approved, without the
  raw `extraction_confidence_tier` column ever changing. Used in both `build_document_response` (the
  single-document/approve response) and the list endpoint's own batched query.

New endpoint: `POST /api/documents/{id}/approve` — 404 if the document has no `FinancialMetrics` row
at all, 400 with a specific message if it isn't actually `needs_review` (nothing to approve, so a
stale UI double-click surfaces clearly instead of silently succeeding at nothing), otherwise sets
`human_approved_at = utcnow()` and returns the document with its promoted effective tier.

Frontend: a new `DocumentReviewSheet` component, triggered by a "Review" icon button next to the
existing "Pending Review" badge on the Documents table. Opens a right-side `Sheet` (the primitive
already existed in `components/ui/sheet.tsx`, but was only ever wired up for the sidebar until now)
showing every extracted figure — revenue, customers, cash, EBITDA, gross/operating margin — with
missing ones rendering "Not reported" rather than a fabricated `0` or a blank, and an "Approve for
dashboard" button.

## Reuse audit (explicit instruction: check for duplicate logic before writing new code)

- **`GET /api/documents/{id}` already returned everything the review panel needs** (`DocumentWithText`
  with a nested `financial_metrics`, via the existing `build_document_response`) — no new backend
  read endpoint was needed, only the new `/approve` write endpoint.
- **`useAsyncData` gained an `enabled` option** (default `true`, every existing caller unaffected)
  instead of the review sheet hand-rolling its own fetch-on-open `useState`/`useEffect` pair. The new
  `useDocumentDetail(documentId, options)` hook in `use-dashboard-data.ts` only fetches while
  `documentId` is non-null — opening one row's review sheet doesn't fetch detail for every row on the
  page.
- **`revenue-chart.tsx`'s private `formatAxisValue` helper was promoted to a shared, exported
  `formatCurrencyShort` in `lib/format.ts`.** It already did exactly the `"250000"` → `"€250K"`
  bucketing the review sheet's own value display needed — writing a second copy would have been the
  overlapping logic the instruction was specifically about avoiding. `revenue-chart.tsx` now imports
  it instead of defining its own.
- **Backend tests reused existing fixtures rather than re-deriving needs_review setup**:
  `test_extraction_confidence_routes.py`'s existing `_mock_extraction`/`_GOVERNANCE_DOC_BASELINE`
  helpers and the same `documents_routes.upload_document(...)` call already used by
  `test_upload_with_partial_deterministic_match_persists_as_needs_review` were reused via a small
  `_upload_needs_review_document` wrapper, rather than hand-rolling a second way to produce a real
  needs_review row. `test_document_list.py`'s existing `_add_document` helper was reused directly for
  the new list-endpoint effective-tier test.

## Verification performed

- `pytest tests/` — 213 passed (6 new: promotion without score-rewrite, 400 on an already-`auto_accept`
  document, 404 on a document with no metrics, idempotent re-approval, the list endpoint's effective
  tier, and a dashboard-eligibility companion to the existing exclusion test).
- `npx vitest run` — 163 passed (11 new: `useApproveDocument`/`useAsyncData`'s `enabled` option/
  `getDocument`/`approveDocument` unit tests, plus 3 Documents-page integration tests covering opening
  the sheet, seeing the extracted values, and the full approve-and-refetch flow).
- `npx tsc --noEmit` and `npx next build` — both clean.
- **Live browser verification against a real running frontend/backend pair**, not just the test suite:
  a throwaway local SQLite database (never the production Railway DB, given a genuinely mutating
  action) was seeded with one real `needs_review` document, the app was built and started for real,
  and Playwright drove the actual flow — confirmed the "Pending Review" badge, the review sheet
  showing the seeded Cash/Customers values with "Not reported" for the rest, clicking Approve, the
  badge disappearing afterward, and (via a direct API call) the approved document's own cash figure
  appearing in `/dashboard/summary` immediately after.
