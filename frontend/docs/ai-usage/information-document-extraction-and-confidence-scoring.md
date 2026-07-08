# AI Usage — feature/information-document-extraction-and-confidence-scoring

## Context

Executed autonomously, per explicit user authorization, while the user was away (session limit
reset). The plan was built and approved in an earlier planning session (`shiny-marinating-rainbow.md`)
across several rounds of user feedback, then executed end-to-end on this branch with no further
questions asked, exactly as instructed.

## What was built

### 1. Information Document extraction

`financial_metrics_extractor.py` gained a second extraction path for Senus's Information Document
(the Euronext listing prospectus) — a genuinely different format from the half-year filing (one
summary table, not three separately-headed statements). Dispatched automatically by section-marker
detection (`_extract_all` tries the half-year format first, falls back to the Information Document
format when its `summary financial information` marker is found instead).

Real extracted values, confirmed against the actual PDF: revenue €836,991 (FY2025) / €688,317
(FY2024), cash €140,135 / €424,639, 36 customers, gross margin 77.5% / 62.8%, operating margin
-75.7% / -164.3%, period "FY2025"/"FY2024". EBITDA and every Solvency/Returns field stay `None` --
genuinely not disclosed in this document, confirmed by direct inspection, not assumed.

**Two real bugs found and fixed while building this, both through actually testing against the real
PDF, not assumed correct:**

- **Narrative leakage in the new section isolator.** The first attempt bounded the Information
  Document's section from `"summary financial information"` to `"bankruptcy"` -- too wide. The real
  document has narrative commentary between the table and that later heading (e.g. "...reflecting
  improved operational efficiency and reductions in cost of sales"), and `cost of sales` matched that
  sentence instead of failing cleanly (the table has no cost-of-sales row at all), pulling in numbers
  from a completely unrelated sentence about administrative expenses. Fixed by bounding to the
  `"profit and loss"` narrative subheading that immediately follows the table instead -- exactly the
  failure mode this extractor was rewritten to avoid in the first place, just found again in a new
  code path.
- **Cadence-cue false positive from whole-document scanning.** A forward-looking sentence 40+ pages
  from the real period statement ("a trading update following completion of the half year ending 31
  December 2025") made a genuinely full-year filing's cadence look ambiguous, because the half-year/
  full-year cue regexes were searched across the entire document text. Fixed by localizing the search
  to a ±200-character window around the actual `"ended DD Month YYYY"` match.

### 2. Extraction confidence service (`backend/app/services/extraction_confidence.py`, new)

A deterministic, transparent point-based scorer (no ML model -- none exists in this pipeline, and
inventing one would itself be a fabrication), tiered per user-specified industry-standard IDP
thresholds: ≥95% auto-accept, 85-94% needs-review, <85% reject. Source-aware: a value the
deterministic extractor found scores higher than the same value found only via Gemini narrative
inference (30 vs. 15 points for revenue, 15 vs. 8 for a secondary field, 15 vs. 8 for the period) --
an unrecognized document format caps the score at 0 regardless of any other field "found" (more
likely coincidental than real). Two independent arithmetic reconciliation checks (P&L: revenue − cost
of sales = gross profit; cash flow: operating + investing + financing = net change in cash) cap the
tier at `needs_review` even at a full point score.

**Wired into the single shared choke point** (`ReportService._generate`), not the two route handlers
-- confirmed by reading the code that `generate_report` is the *only* entry point that ever calls
`_generate`, used identically by manual upload, the investor-relations import, and report
regeneration. This makes the gate structurally impossible to bypass from any future ingestion path,
not just the two that existed when this was built.

**A real architectural bug found while testing the rejection path, not assumed to work from the
design alone**: `ReportService.generate_report` already commits a "generating"-status `Report` row
*before* `_generate`'s confidence check ever runs (to atomically claim the generation against
concurrent requests -- a pre-existing, legitimate pattern). A plain `db.rollback()` in the calling
route therefore had nothing left to undo -- the Document (and the claimed Report) were already
durable. Confirmed with a real test that initially failed with the "rejected" document still present
in the database. Fixed by explicitly deleting the Document (new-document paths) or restoring the
Report's previous status (regenerate path) rather than relying on rollback.

**A second real bug found via live testing against the real Information Document, unrelated to the
new dispatch code**: `gemini_service.py`'s `_empty_response()` safe-fallback (returned whenever
Gemini is unavailable, rate-limited, or fails) hardcoded `"ebitda": 0` and zeros for every other
financial field. Since Gemini is only ever called when the deterministic baseline is *incomplete*
(`_baseline_is_complete`), this fallback fires exactly when a field is genuinely missing -- and the
merge logic (baseline wins only where non-`None`) let the fabricated `0` silently stand in for the
Information Document's genuinely-undisclosed EBITDA. The exact same "missing becomes a fake zero"
bug already fixed once in `report_service.py`'s `_normalize_metric` this session, just living in a
different file. Found by noticing `ebitda: 0.0` in a live API response where `None` was expected --
not caught by any existing test, since no prior document had ever had a genuinely incomplete
baseline reach this fallback path in a test. Fixed, and a stale test asserting the old `0` behavior
was corrected to assert `None`.

### 3. Cadence-mismatch protection (`GET /metrics/dashboard/revenue-trend`)

The Information Document (12-month) and the half-year filing (6-month) must never be blended into
one trend line implying regular, comparable periods -- confirmed as a real risk, not hypothetical:
verified end-to-end that uploading both real filings together produces a revenue-trend response
containing *only* the half-year filing's own prior-period comparative, correctly excluding the
Information Document's row. A row is excluded only on a *confirmed* mismatch (both its own cadence
and the latest row's are known and differ) -- an unknown cadence (most existing test fixtures, and
some real filings) is never treated as evidence of a mismatch.

### 4. Exec-view confidence boundary

`/dashboard/summary` and `/dashboard/revenue-trend` only select `FinancialMetrics` rows with
`extraction_confidence >= 95` (or `NULL`, for rows scored before this feature existed) -- a
`needs_review` document is real, persisted, and visible via the Documents table's muted "Pending
Review" tag, but never silently drives the board-facing headline numbers.

### Frontend

- `DocumentItem`/`FinancialMetricsResponse` gained `extraction_confidence`/`extraction_confidence_tier`.
- Documents table: a muted, neutral "Pending Review" `Badge` (not red/green -- that vocabulary is
  reserved for real trend/variance, per explicit user correction mid-planning) shown only for
  `needs_review`, backed by a new batched query in `list_documents()` (same pattern as
  `_ai_reporting_periods_by_document`, not a reintroduced N+1).
- A global "All figures in EUR · Data as of {date}" banner on the main dashboard, backed by a new
  `data_extracted_at` field on `DashboardSummaryResponse`.
- The "View source PDF" link already existed (PR #30) -- confirmed sufficient as the scoped version
  of "traceability" for this pass; full deep-linked bounding-box highlighting requires positional PDF
  extraction this project doesn't do yet, logged as a real future item in `docs/roadmap.md` rather
  than attempted here.
- Reports table does **not** yet show the same tag (would need the same batched-query treatment
  applied to `list_reports`, not done here given time -- noted honestly in `docs/roadmap.md` and the
  README rather than silently skipped).

### Explicitly scoped out, and why

A large batch of enterprise IDP best-practice suggestions (hover-to-source with bounding boxes, a
full HITL staging queue with side-by-side correction UI and audit logging, ERP master-data
cross-referencing, duplicate invoice detection, currency-code flags, handwriting detection) was
evaluated against what this project actually is -- a single-user boardroom tool ingesting a handful
of company-level financial statements, not an invoice/AP automation pipeline against ERP data. Most
of the list doesn't map onto this project's real risk profile; the parts that did (confidence
badging, "as-of" dates, mathematical reconciliation) were adopted. This reasoning is recorded in full
in the plan file and distilled into `docs/roadmap.md`, rather than either silently ignoring the
feedback or force-building UI the product doesn't need.

## Verification performed

- `pytest tests/` -- 167 passed (34 new: `test_extraction_confidence.py` for the scoring function in
  isolation, `test_extraction_confidence_routes.py` for the route-level gate using a real
  `ReportService` with mocked extraction internals, new tests in
  `test_financial_metrics_extractor.py` against the real Information Document PDF fixture, new tests
  in `test_metrics_summary.py` and `test_document_list.py`, a corrected test in
  `test_gemini_service.py`).
- `npx vitest run` -- 129 passed.
- `npx tsc --noEmit` -- no errors.
- `npx next build` -- succeeds.
- **End-to-end against the real Information Document and the real investor relations API**, on a
  throwaway local database (never production, per this project's standing rule), after several false
  starts caused by stale background server processes from earlier in the session (a `python3.11.exe`
  process, a different image name than the `python.exe` filter used to hunt for it, silently held
  port 8010 and served pre-fix code for several verification attempts before being found):
  1. Uploaded the real Information Document PDF -- confirmed real FY2025 figures (not nulls, not
     zeros), `extraction_confidence: 100.0`, `tier: auto_accept`.
  2. Attempted importing a real governance filing (the AGM proxy notice) via the live investor
     relations API -- confirmed `422` with a real, computed confidence score (`0%`) and a clear
     explanation, and confirmed zero documents were persisted.
  3. Uploaded the real half-year filing alongside the Information Document -- confirmed
     `/dashboard/revenue-trend` correctly excluded the mismatched-cadence row, and
     `/dashboard/summary` correctly showed the more recent (half-year) filing's data.
