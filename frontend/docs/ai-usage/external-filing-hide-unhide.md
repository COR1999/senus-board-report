# AI Usage — feature/external-filing-hide-unhide

## Context

User request, directly from a screenshot showing a rejected import (0% confidence, "likely not a
financial statement at all") sitting alongside the "5 new filings available" banner: add a way to
mark a filing as out of scope so it doesn't keep cluttering the space.

## The real gap

A rejected import (the extraction confidence gate, PR #42) creates no `Document` row at all, by
design — nothing gets persisted for a failed attempt. That's correct for keeping junk data off the
dashboard, but it also meant there was no durable record of "the user already looked at this and
confirmed it's not a financial statement" — every governance filing (AGM notices, Memo & Articles)
would keep showing up in the "new filings available" banner on every single page load, forever, with
no way to dismiss it.

## What was built

- `backend/app/models/hidden_external_filing.py` — a new `HiddenExternalFiling` table
  (`attachment_id` unique, plus a metadata snapshot: `file_name`/`file_size`/`published_date`/
  `hidden_at`). Snapshotted rather than re-fetched from the IR API on every read, so a hidden entry
  stays displayable even if the IR API later changes or stops listing that filing. No migration
  needed beyond adding the model to `app/models/__init__.py` — this project has no Alembic, and a
  brand-new table is picked up automatically by the existing `Base.metadata.create_all` on startup
  (unlike a new *column* on an existing table, which needs the idempotent `_add_missing_columns`
  pattern).
- Three new routes in `documents.py`: `GET /external/hidden` (list), `POST
  /external/{attachment_id}/hide`, `POST /external/{attachment_id}/unhide` — all idempotent (hiding
  an already-hidden filing or unhiding a never-hidden one just no-ops rather than erroring).
  `GET /external/available` now also excludes anything hidden, alongside its existing
  attachment_id/filename dedup checks.
- Frontend: a small "hide" (eye-off) icon button next to each available filing's existing Import
  button, and a new, muted "Out of scope (N)" card below it (only rendered when non-empty) listing
  hidden filings with a one-click "Restore" button each.

## A real API-shape bug found while wiring the frontend

`unhideExternalFiling`'s first draft went through the shared `apiFetch` helper (which always calls
`res.json()`), but the backend's `unhide` route returns a bodyless `204 No Content` — `res.json()`
throws on an empty body. Caught before merge by writing a plain test asserting the promise actually
resolves to `undefined`, not just that the right URL was hit. Fixed the same way `deleteDocument`
already handles this (a raw `fetch` + `res.ok` check, no `.json()` call at all) rather than adding a
special case to the shared helper.

## Verification performed

- `pytest tests/` — 184 passed (7 new: hide excludes from available, hide is idempotent, hide 404s on
  an unknown attachment_id, the hidden list shows what was hidden and stays stable even if the IR API
  stops listing it, unhide restores to available, unhide is idempotent for something never hidden).
- `npx vitest run` — 146 passed (8 new: data-service fetcher tests including the 204-body regression,
  and Documents-page tests for the hide button, the "Out of scope" section appearing/not-appearing,
  and restore).
- `npx tsc --noEmit` / `npx next build` — both clean.
