# AI Usage — feature/investor-relations-filing-sync

## What was built

Originally believed Senus had only ever published one financial document (the
half-year results already ingested). A more thorough look at the investor
relations page turned up more filings and, via inspecting the page's own
network requests (Playwright), the plain JSON REST API the page's SPA is
built on (`api.app.assiduous.tech/v1/investor-relations/senus/*` — see the
root README's "Investor relations API" section). This feature wraps that
external API so new filings can be checked for and imported without a
manual download/re-upload round-trip.

Two design decisions were confirmed with the user before building (both
explicitly flagged as open questions when the idea was first noted in
`docs/roadmap.md`):

- **Approval-gated, not silent auto-ingest.** A "new filing available" banner
  on the Documents page with an explicit **Import** button per filing —
  never automatic.
- **Checked on demand** (page load, or a manual **Check now** button), not a
  background poller / scheduled cron.

### Backend

- `app/services/investor_relations_client.py` (new) — `list_available_filings()`,
  `find_filing(attachment_id)`, `download_filing(attachment_id)` against the
  real API via `httpx` (already a dependency). Only the `documents` and
  `reports` categories are queried — `corporate` (presentations) and
  `regulatory` (press releases/AGM notices) don't carry extractable
  financial-statement data (confirmed by manually inspecting a sample of
  each, see `backend/docs/source-documents/README.md`).
- `Document.external_attachment_id` (new, nullable, unique) — set only for
  documents imported via this feature; `NULL` for manual uploads. Lets the
  "available" check know what's already in the system without re-downloading
  every candidate to hash it. Migrated via the existing idempotent
  `_add_missing_columns` mechanism (no Alembic in this project).
- `upload_document`'s body was refactored into a shared `_ingest_document(content,
  filename, db, external_attachment_id=None)` helper in `documents.py`, used
  by both the manual upload route and the new import route — so
  extraction/content-hash-dedup/report-generation logic lives in exactly one
  place and the existing dedup protection applies to IR-imported filings for
  free.
- `GET /api/documents/external/available` — lists filings not yet imported.
  Filtered by **both** `attachment_id` and `filename`, not just the former:
  the real API lists the same underlying filing under different
  `attachmentId`s across its `documents`/`reports` categories, and the
  half-year filing (manually uploaded, so its `external_attachment_id` is
  `NULL`) would otherwise wrongly show up as "new" every time.
- `POST /api/documents/external/{attachment_id}/import` — looks up the
  filing's metadata, downloads it, and ingests it via `_ingest_document`.

### Frontend

- `data-service.ts`: `getAvailableExternalFilings()` (fails silently to `[]`
  on an unreachable IR API, same fallback policy as the other GET helpers)
  and `importExternalFiling(attachmentId)` (throws on failure, same as
  `uploadPDF`/`deleteDocument`).
- `use-dashboard-data.ts`: `useAvailableExternalFilings()` — a plain
  `useAsyncData` call with no `pollIntervalMs`, matching the "check on
  demand" decision.
- `use-mutations.ts`: `useImportExternalFiling(onSuccess)`, same shape as
  `useUploadDocument`/`useDeleteDocument`.
- `app/documents/page.tsx`: a banner above the table when filings are
  available (name/size/published date + Import button per filing, plus a
  "Check now" button), and a quiet one-line "No new filings..." + "Check now"
  affordance when the list is empty — so the manual check is always
  reachable, not only when something is already pending. Importing refetches
  both the documents list and the available-filings list.

## Notable decisions made along the way

- **Filename fallback for dedup, not just `attachment_id`** — this wasn't a
  hypothetical edge case: re-running the real API this session confirmed the
  already-ingested half-year filing is listed there too, and an
  `attachment_id`-only check would have shown it as "new" and let it be
  re-imported (creating a genuine duplicate, only caught downstream by the
  content-hash 409 rather than being excluded from the list in the first
  place).
- **Everything in the `documents`/`reports` categories is shown, not just
  filenames that "look financial."** The real API's `documents` category
  turned out to mix real financial statements (a company balance sheet) with
  governance documents (AGM notices, Memorandum & Articles of Association).
  Rather than build a brittle filename classifier, the approval-gated design
  already covers this: a human sees the actual filename before clicking
  Import, so a "Notice of Annual General Meeting 2026" being visible in the
  list (and presumably left un-imported) is a feature of the design, not a
  gap in it.
- **No polling, no cron** — deliberately narrower than the original
  "automated sync" idea's name suggests, per explicit product direction.

## Verification performed

- `cd backend && python -m pytest tests/ -q` — 128 passed (118 pre-existing +
  10 new: 3 for the `investor_relations_client` service mocking `httpx`, 7
  for the two routes covering both exclusion cases, the 502-on-unreachable
  path, a successful import, a 404 on an unknown `attachment_id`, and a 409
  on re-importing the same filing).
- `cd frontend && npx vitest run` — 125 passed (adds banner-rendering,
  import, and "Check now" tests to `documents/page.test.tsx`, hook tests for
  `useImportExternalFiling`, and a `getAvailableExternalFilings`
  fail-silently test).
- `cd frontend && npx tsc --noEmit` — no errors.
- `cd frontend && npx next build` — succeeds.
- **End-to-end against the real investor relations API** (not mocks): ran
  the backend locally against a throwaway SQLite database (never against
  production, per this project's standing rule about the live Railway DB),
  and:
  1. Called `GET /external/available` against an empty database — it
     returned all 7 real filings currently on Senus's IR page, including
     ones not previously catalogued this session (AGM proxy/notice
     documents, a Memo & Articles document, a standalone balance sheet).
  2. Uploaded the real half-year filing PDF (from `backend/tests/fixtures/`)
     through the actual `/api/documents/upload` endpoint to simulate
     "already imported", then re-called `/external/available` and confirmed
     it was excluded by filename match — proving the dedup logic works
     against the real API's actual duplicate-listing behavior, not just a
     hand-constructed test fixture.
  3. Called `POST /external/{attachment_id}/import` for the real ADF Farm
     Solutions filing — it downloaded the actual 7MB PDF from Senus's API
     and ran it through the real extraction pipeline, returning a genuine
     `Document` row with extracted text.
  4. Confirmed the imported filing disappeared from a subsequent
     `/external/available` call.
  5. Confirmed re-importing the same `attachment_id` returned `409`, and an
     unknown `attachment_id` returned `404`.
  6. Torn down the throwaway local server and database afterward — nothing
     from this verification touched production.
