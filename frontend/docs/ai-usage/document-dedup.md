# AI Usage — feature/document-dedup

## What was built

The deferred roadmap item: uploading the same PDF twice created two separate
`Document` rows with no duplicate detection anywhere in the backend.

Design decision (confirmed with the user before building, since it was
explicitly flagged as an open question when this was deferred): **detect by
content hash (SHA256 of the uploaded bytes), and block the upload with a 409**
rather than filename-matching or a warn-but-allow flow. Content hash was
chosen over filename because it catches a renamed re-upload of the same PDF
and never false-positives on two genuinely different files that happen to
share a filename.

- **Backend**: `POST /api/documents/upload` now hashes the file, checks for
  an existing `Document` with the same `content_hash` before doing any
  processing, and returns `409 {"detail": "This exact file was already
  uploaded as document #N on <date>."}` if found. A `content_hash` column
  (nullable, unique via a separate index) was added to `Document`. Also
  wrapped the insert in a try/except for `IntegrityError` as a belt-and-
  suspenders race-condition guard (two near-simultaneous uploads of the same
  file), on top of the pre-check.
- **Migration**: existing rows get `NULL` content_hash (both SQLite and
  Postgres allow multiple NULLs through a unique index, so this doesn't need
  backfilling for the constraint itself to work). Found along the way that
  SQLite's `ALTER TABLE ADD COLUMN` rejects an inline `UNIQUE` modifier
  (Postgres allows it) -- fixed by adding the column and the unique index as
  two separate, both-portable statements (`ADD COLUMN` then a separate
  `CREATE UNIQUE INDEX IF NOT EXISTS`).
- **`_add_missing_columns` fix**: this was the first time a *second* table
  was ever added to `_COLUMNS_ADDED_AFTER_INITIAL_RELEASE` (previously only
  `financial_metrics`) -- doing so exposed a latent bug where the helper
  would raise `NoSuchTableError` if any tracked table didn't exist yet in
  whatever DB it's pointed at (harmless in real production, where `documents`
  has always existed, but broke two existing migration tests that only
  create a scratch `financial_metrics` table). Fixed by checking table
  existence first and skipping tables that aren't there yet.
- **Frontend**: `uploadPDF()` previously threw a generic `Failed to upload
  PDF: Conflict` on any non-2xx response -- the specific duplicate-document
  message never reached the user, since `HTTPException`'s JSON body
  (`{"detail": "..."}`) was never parsed. Fixed to read `detail` from the
  error body when present, falling back to the generic message otherwise.
  No other frontend change was needed: the `/documents` page's existing
  error banner (from `feature/api-integration-layer`) already surfaces
  whatever `uploadError` string it's given.

## A real bug found while verifying against the real production DB (not from AI generation)

Live-testing the dedup fix against the actual Railway/production database
(re-uploading the real Senus filing PDF) surfaced a second, unrelated,
pre-existing bug: **`DELETE /api/documents/{id}` failed with a
`ForeignKeyViolationError` on any document that actually had
FinancialMetrics/Report rows attached** -- i.e. every successfully processed
document, the common case. The route used a bulk `delete(Document).where(...)`
SQL statement, which issues a direct DELETE that bypasses the ORM's
`cascade="all, delete-orphan"` on `Document`'s relationships (there's no
DB-level `ON DELETE CASCADE` foreign key backing it). This had shipped in
`feature/document-report-actions` and was never caught because no test ever
exercised deleting a document with real child rows -- the only existing
delete-related work was frontend wiring, assuming the backend endpoint
"already existed" and worked.

Fixed by loading the ORM instance (`db.get(Document, id)`) and deleting it
through the session (`db.delete(document)`) instead of the bulk statement, so
the cascade fires correctly. Added the two tests that should have existed
from the start (delete-with-children, delete-nonexistent-404).

**This was caught by actually testing end-to-end against the real DB**, not
by unit tests or code review -- verifying the dedup fix meant re-uploading
the real filing PDF and then needing to clean up the resulting duplicate,
which is exactly the scenario the pre-existing bug was hiding in.

## Notable decisions made along the way

- **Content hash + block, confirmed with the user** rather than assumed --
  this was explicitly left as an open design question when the bug was
  first found and deferred, so it warranted asking rather than guessing.
- **Pre-check query, not just a DB constraint**: the unique index is the
  real correctness guarantee (handles races), but a plain `IntegrityError`
  alone would surface as a generic 500 -- the pre-check exists specifically
  to produce the clear, specific 409 message in the common (non-racing) case.
- **Test isolation**: both new test files (`test_document_dedup.py`,
  `test_document_delete.py`) use their own function-scoped in-memory SQLite
  engine rather than conftest's shared session-scoped one -- the routes
  under test do real `db.commit()`s (by design), which would otherwise leak
  committed rows into every other test file sharing that engine. Caught this
  by actually running the full suite after adding the first version of these
  tests and seeing unrelated tests fail with polluted data.

## Verification performed

- `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q` — 103 passed
  (94 pre-existing + 5 dedup + 2 migration + 2 delete-cascade regression).
- `cd frontend && npx vitest run` — 105 passed.
- `cd frontend && npx tsc --noEmit` — no errors.
- `cd frontend && npx next build` — succeeds.
- End-to-end against the real production DB: ran the backend locally against
  the live Railway Postgres, confirmed the `content_hash` column migration
  applied cleanly on startup, then actually re-uploaded the real Senus
  filing PDF and confirmed the flow end-to-end:
  1. First re-upload succeeded (expected -- the pre-existing document had
     never been backfilled with a hash), creating an unwanted real duplicate.
  2. A second re-upload was correctly rejected (409) against that new
     duplicate, proving the dedup logic itself works.
  3. Found the delete-cascade bug while trying to clean up the duplicate.
  4. Manually cleaned up the duplicate's rows, fixed the delete route, then
     backfilled `content_hash` on the real original document (id 3) from the
     actual PDF bytes on disk.
  5. Re-uploaded the real PDF one more time and confirmed it was rejected
     immediately: `{"detail": "This exact file was already uploaded as
     document #3 on 2026-07-06."}`.
  6. Confirmed the document list is back to exactly one row.
- Not yet deployed: this only exists on `feature/document-dedup` locally.
