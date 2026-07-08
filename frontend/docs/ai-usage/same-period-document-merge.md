# AI Usage — fix/same-period-document-merge

## Context

Flagged directly by the user while using the live production app, immediately after PR #53's fix
deployed: re-uploading ADF Farm Solutions produced a new document with a real, derivable reporting
period (id 37) — and the period selector immediately showed **two entries with the identical label**
("FY2025 (Jul 2024 – Jun 2025)"), one for the new upload and one for the already-existing Information
Document (id 14). No way to tell them apart, and picking one vs. the other returned different KPI
values, since each document was missing a different field.

## Investigation before proposing anything

Compared both documents' real extracted figures directly via the production API before designing a
fix:

| field | doc 37 (ADF, vision-extracted) | doc 14 (Information Document, text-extracted) |
|---|---|---|
| revenue | 836,991 | 836,991 (identical) |
| cash | 140,135 | 140,135 (identical) |
| gross_margin / operating_margin | 77.47% / -75.71% | 77.47% / -75.71% (identical) |
| customers | null | 36 |
| ebitda | -613,313 | null |

Every field both documents reported agreed exactly (two independent extraction paths — Gemini vision
and deterministic text parsing — confirming each other), and each document filled a genuine gap the
other had. This was a safe merge opportunity, not a "which source do we trust" problem — confirmed
with the user before any design work started.

Also checked whether more real financial data exists anywhere on Senus's investor-relations platform
(the user asked directly): `GET /api/documents/external/available` (the existing, already-built API
integration — not a page-scrape) currently lists exactly 4 not-yet-imported filings, none of them
financial statements (an AGM proxy form, an AGM circular notice, "Memo and Arts", and the Balance
Sheet, already correctly rejected once before at 55% confidence). No missing real financial data
found.

## Design decisions (confirmed with the user via AskUserQuestion before building)

- **A genuine field-level conflict must go to a human to review, not be silently resolved.** Reuses
  the exact `needs_review`/review-panel/approve infrastructure already built in PR #52, rather than
  inventing a new mechanism.
- **Both original source documents stay fully intact and independently visible/downloadable.**
  Nothing is deleted or hidden. A **new** record represents the merged period.
- **Prevent this going forward, not just fix the current two documents.** Every future upload/import
  checks whether its derived reporting period already matches an existing eligible document.

## The fix

**Reused the existing `Document`/`Report`/`FinancialMetrics` triad for the merged record — no new
tables.** A merge is just another ordinary Document (synthetic filename, no `file_path` since there's
no single source PDF) + Report + FinancialMetrics row. This means the entire existing Documents page,
review panel, approve workflow, and dashboard-eligibility filters work on it automatically, with zero
new UI concepts.

New `FinancialMetrics.superseded_by_document_id` column marks both original rows once merged.
`_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` (`metrics.py`, already the single shared eligibility gate for
`/dashboard/periods`, `/dashboard/summary`, and `/dashboard/revenue-trend`) was extended with `and_(...,
superseded_by_document_id.is_(None))` — one change, all three call sites protected simultaneously,
rather than adding the check separately at each site.

New `backend/app/services/period_merge_service.py`:
- `find_same_period_match` — an existing, eligible row sharing the new row's exact
  `reporting_period_start`/`_end`.
- `merge_documents` — field-level union across the six core figures (revenue/customers/cash/ebitda/
  gross_margin/operating_margin): a gap (one side null) is filled without flagging anything; an
  agreement (both non-null, equal within float tolerance) is used as-is; a genuine conflict uses the
  existing (first-seen) source's value provisionally and records both candidate values plus their
  source filenames in `extraction_confidence_reasons`, tagging the merged row `needs_review` instead
  of `auto_accept`.
- `reconcile_all_periods` — a sweep for documents that predate this fix, used by the new
  `POST /api/documents/reconcile-periods` endpoint. Idempotent: an already-superseded row is never
  re-matched.

Wired into `documents.py`'s `_ingest_document` as a separate, additive follow-up step *after* the new
document finishes ingesting completely and normally on its own — the new upload's own
Document/Report/FinancialMetrics are never affected by whether a merge subsequently happens.

## Reuse audit

- No new tables — the merge is just another `Document`/`Report`/`FinancialMetrics` triad.
- `_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` extended once, not duplicated across three endpoints.
- A genuine conflict reuses the `needs_review` tier and `extraction_confidence_reasons` field (from
  PR #52) exactly as designed for a human to review via the existing `DocumentReviewSheet` — no new
  review UI.
- The "Merged" tag on the Documents page reuses the exact same table-badge pattern as "Pending
  Review"/"Rejected".

## Verification performed

- `pytest tests/` — 221 passed (5 new: a clean gap-fill merge produces `auto_accept` with both
  documents' unique fields present; a genuine conflict produces `needs_review` with both values and
  source filenames named in the reasons; documents with genuinely different periods are never merged;
  `/dashboard/periods` shows one entry, not two, after a merge; the reconcile endpoint is idempotent).
- `npx vitest run` / `tsc --noEmit` / `next build` — 166 passed, both clean.
- Diagnosed against real production data (direct API calls comparing both documents' actual figures)
  before writing any code, not guessed or reproduced only locally.
- **Production fix applied with the user's explicit go-ahead**: called the new
  `POST /api/documents/reconcile-periods` endpoint once against real production to merge documents 37
  and 14, confirmed `/metrics/dashboard/periods` afterward shows a single, complete FY2025 entry.
