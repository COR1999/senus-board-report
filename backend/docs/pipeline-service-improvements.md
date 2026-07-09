# Pipeline Service Improvements (feature/pipeline_service)

## Summary

This change set covers three areas of the backend pipeline: making the
deterministic financial-metrics extractor more reliable on real OCR'd
tables, adding quota protection around the Gemini AI enrichment layer, and
consolidating the API route surface to remove duplicate/unused endpoints.

## What changed

### 1. Financial metrics extractor (`financial_metrics_extractor.py`)

- Added `_is_number(token)`: an anchored-regex token classifier that
  distinguishes real financial values (`"354,813"`, `"354.8k"`, `"1.2m"`,
  `"-120,000"`, `"€354,813"`, `"(120,000)"`) from labels/narrative text
  (`"Turnover"`, `"EBITDA"`, `"FY2028"`, `"%"`, `"positive"`).
- Fixed `_find_value_same_line`, which previously accepted any token
  containing a digit (so `"FY2028"` on a same-line match would have passed
  through) — now uses `_is_number`.
- Fixed `_find_value_next_line`, which previously returned the raw next
  line unsplit. On a two-column OCR row (`"354,813   340,931"`, current +
  prior year), the old code passed the whole string to `_to_number` and
  silently got `0` back. It now returns the first token that passes
  `_is_number`.
- Added `extract_statement_text(text, max_chars)`: a public method that
  returns just the isolated P&L / balance sheet / cash flow sections,
  for use by callers that need a compact, statement-only view of a
  document instead of raw text (see Gemini prompt change below).

### 2. Gemini quota protection (`gemini_service.py`, `report_service.py`)

- `ReportService.generate_report` now atomically claims a report row
  (`UPDATE ... WHERE status != 'generating' SET status = 'generating'`)
  before calling `_generate`, so overlapping requests for the same
  document (double-click regenerate, retried request) can't both fire a
  Gemini call for the same document.
- `GeminiAnalysisService` gained a proactive rate limiter — a per-minute
  cap (`GEMINI_MAX_CALLS_PER_MINUTE`, default 10) and a rolling 24h cap
  (`GEMINI_MAX_CALLS_PER_DAY`, default 1000) — checked *before* calling the
  API, on top of the existing reactive 429 backoff and 24h response cache.
- `report_service._build_prompt` now sends
  `FinancialMetricsExtractor.extract_statement_text(...)` instead of raw
  `text[:8000]`, so the AI prompt contains the actual P&L/balance-sheet
  tables instead of whatever happened to be in the first 8000 characters
  (often cover page / TOC / narrative).
- New env vars documented in `.env.example`:
  `GEMINI_MAX_CALLS_PER_MINUTE`, `GEMINI_MAX_CALLS_PER_DAY`.

### 3. API route consolidation

Removed duplicate/unused endpoints and dead code across `documents.py`,
`reports.py`, and `metrics.py`:

- Removed `POST /api/documents/{id}/regenerate-report` (duplicate of
  `POST /api/reports/{report_id}/regenerate`, which is now the one
  canonical regenerate endpoint).
- Removed the dead, commented-out duplicate of the `/dashboard` handler
  sitting above the real one in `reports.py`.
- Added the missing `GET /api/reports` (list all reports) route —
  `ReportService.list_reports()` already supported this but it was never
  mounted.
- Removed manual metrics CRUD from `metrics.py`
  (`POST /metrics`, `GET /metrics`, `GET /metrics/{document_id}`, and
  `GET /metrics/report/{id}/detailed`) since metrics are always written
  internally by report generation and never by a client, and the
  `/detailed` view duplicated `GET /api/reports/{id}/dashboard`. Only
  `GET /metrics/dashboard/summary` remains.
- Updated `tests/test_upload_metrics.py` to drop the test that exercised
  the now-removed `create_metrics` endpoint.

Route surface at the time of this change (many routes have been added since --
see `backend/README.md`'s "Route surface" table for the current, up-to-date list):

| Router | Routes |
|---|---|
| documents | `GET /api/documents`, `POST /api/documents/upload`, `GET/DELETE /api/documents/{id}` |
| reports | `GET /api/reports`, `GET/POST /api/reports/document/{id}`, `GET/DELETE /api/reports/{id}`, `GET /api/reports/{id}/dashboard`, `POST /api/reports/{id}/regenerate` |
| metrics | `GET /metrics/dashboard/summary` |

## Files involved

- [backend/app/services/financial_metrics_extractor.py](backend/app/services/financial_metrics_extractor.py)
- [backend/app/services/gemini_service.py](backend/app/services/gemini_service.py)
- [backend/app/services/report_service.py](backend/app/services/report_service.py)
- [backend/app/api/routes/documents.py](backend/app/api/routes/documents.py)
- [backend/app/api/routes/reports.py](backend/app/api/routes/reports.py)
- [backend/app/api/routes/metrics.py](backend/app/api/routes/metrics.py)
- [backend/tests/test_upload_metrics.py](backend/tests/test_upload_metrics.py)
- [backend/.env.example](backend/.env.example)

## Verification

- `python -m py_compile` on all edited modules.
- Standalone sanity script exercising `_is_number` against the full
  true/false case list from the design discussion, plus an `extract()`
  run over a synthetic OCR sample with narrative padding, a two-column
  P&L row, and a balance sheet — confirmed revenue/ebitda/cash extract
  correctly and narrative years are never picked up.
- Standalone script exercising the Gemini rate limiter's per-minute and
  per-day caps directly (env-configured to low thresholds) — confirmed
  both trip correctly.
- `GET /openapi.json` via `TestClient` to confirm the final route table
  matches the consolidation above exactly (no orphaned duplicate paths).
- Ran the surviving upload/metrics test function manually (no working
  pytest install in this environment) to confirm it still passes after
  removing the CRUD test.

## Known issues found during review

A multi-angle code review of the full branch diff (`git diff main`)
surfaced 10 confirmed issues, most severe first. The top two were
regressions in this change set's own concurrency guard and have been
fixed; the rest are pre-existing and still open.

### Fixed

1. **Stuck "generating" reports couldn't be recovered.** The atomic claim's
   `WHERE status != "generating"` was unconditional, so a crash mid-generation
   left a report permanently stuck, with no escape even via `force=True`.
   Fixed by adding `ReportService.GENERATION_STALE_AFTER` (10 minutes): a
   report still marked `"generating"` past that age is treated as
   belonging to a dead worker and becomes reclaimable again (checked both
   in the early-return fast path and in the claim's `WHERE` clause via
   `OR updated_at < now - stale_after`), regardless of `force`. A genuinely
   in-flight (non-stale) generation still can't be interrupted.
2. **Unguarded insert race on first-time `Report` creation.** Two
   concurrent requests for a brand-new document could both pass the
   "no report yet" check and the second commit would raise an unhandled
   `IntegrityError` (`Report.document_id` is unique). Fixed by wrapping
   that insert in a try/except: on `IntegrityError`, roll back and
   re-select the row the other request just committed instead of
   crashing.

Verified with a real (non-mocked) SQLite-backed session: a
manufactured stale-`"generating"` report is reclaimed and regenerated,
a fresh (non-stale) `"generating"` report is left alone, and a forced
unique-constraint conflict is caught and correctly recovers to the
winning row.

### Fixed (round 2)

3. **`_to_number` couldn't convert tokens `_is_number` classified as
   valid.** Parenthesized negatives (`"(120,000)"`) and `£`-prefixed
   values (`"£354,813"`) both raised `ValueError` inside `float()` and
   silently returned `0`. Fixed by stripping `£` alongside the existing
   `€`/`$`/`,` stripping, and by detecting a fully-parenthesized value
   and negating the parsed result.
4. **`_find_value_next_line`'s non-numeric fallback broke the
   `_extract_table_value` fallback chain.** It used to return the raw
   next line verbatim when no token on it passed `_is_number`. Since
   `_extract_table_value` does
   `_find_value_next_line(...) or _find_value_same_line(...)`, that
   truthy-but-non-numeric string short-circuited the `or`, so a value
   that was actually present on the *same* line as the label was never
   found whenever the next line happened to be narrative text. Fixed by
   returning `None` instead of the raw line, so the `or` now falls
   through to `_find_value_same_line` correctly.
5. **The reactive 429 backoff never persisted.** `_ai_disabled_until` is
   a class attribute, but `_disable_ai_temporarily` set it via
   `self._ai_disabled_until = ...` (a bare instance assignment), which
   only shadowed the class attribute on that one instance. Since
   `ReportService.__init__` creates a fresh `GeminiAnalysisService()`
   per request, the circuit breaker was silently defeated — the next
   request's new instance never saw the disabled state. Fixed by writing
   through `GeminiAnalysisService._ai_disabled_until = ...`, matching the
   pattern `_record_call` already used correctly for
   `_daily_call_count`. Verified with a standalone script: disabling on
   one instance is now visible on a brand-new instance constructed
   immediately after.
6. **`_baseline_is_complete` / the metrics merge treated a legitimate `0`
   as "missing."** A pre-revenue or break-even company with a real
   EBITDA of `0` was indistinguishable from "EBITDA not found in the
   document," which (a) burned an unneeded Gemini call when the baseline
   was actually complete, and (b) let a hallucinated non-zero AI value
   override a correct baseline zero in the merge. Fixed by having
   `FinancialMetricsExtractor.extract()` return `None` for fields it
   genuinely couldn't find (as opposed to `0` for a found-and-zero
   value), and updating both `_baseline_is_complete` and the merge loop
   in `report_service._generate` to check `is not None` instead of
   `not in (None, 0)`. Verified with a real (non-mocked) SQLite-backed
   `ReportService.generate_report` run: a document with a complete
   baseline (including a real EBITDA of `0`) skips the Gemini call
   entirely, and a document missing one field still lets baseline win
   for every field it *did* find while accepting the AI value only for
   the field it didn't.

### Fixed during the 2026-07-06 cleanup pass

7. `report.summary["metrics"]` mixing plain floats and `{"value": N}`
   dicts, `tests/test_integration.py` / `app/utils/test_gemini_integration.py`
   calling removed methods, and `docs/frontend-api-routes.md` documenting
   removed endpoints were all addressed. See
   `docs/backend-cleanup-2026-07.md` for the full write-up.
