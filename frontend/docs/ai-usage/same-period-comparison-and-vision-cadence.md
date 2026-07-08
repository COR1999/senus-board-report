# AI Usage — fix/same-period-comparison-and-vision-cadence

## Context

Directly after PR #52 deployed and the user approved the real ADF Farm Solutions document into
production (via the newly-shipped review/approve workflow), they asked: *"why is that new pdf not
comparing versus the year prior"* — a real, live question about the actual deployed app, not a
hypothetical. Investigated against real production API responses before writing any code.

## The bug(s)

Confirmed via `curl` against the real deployed backend:

```json
"revenue": { "value": "€837K", "change": 0.0, "trend": "neutral", "history": [354813.0, 836991.0, 836991.0] }
```

A `change` of exactly `0.0` with `history` ending in two identical `836991.0` values was the tell —
ADF's revenue was being diffed against a document reporting the *same* number, not genuinely "no
prior data".

Two independent root causes, both confirmed by reading the actual code path rather than guessing:

1. `_cadence_months()` (metrics.py) needs `reporting_period_start`/`_end` calendar labels
   (e.g. "Jul 2024"/"Jun 2025") to compute a cadence. The deterministic extractor derives these from
   a filing's full text; Gemini vision extraction (ADF's path, since it's a scanned PDF) only ever
   returns a bare `reporting_period` string like "Financial year ended 30 June 2025" — no start/end
   fields at all. Cadence came back `None` for ADF, so PR #43's mixed-cadence safety filter (which
   deliberately never treats an *unknown* cadence as a mismatch) had nothing to work with.
2. Even with cadence known, ADF and the Information Document are both genuine 12-month FY2025
   filings — same cadence, so cadence-matching alone doesn't distinguish "two different years" from
   "two documents describing the same year". `previous = rows[1]` picked the Information Document
   purely because it was the next most recently *extracted* row, with no check for whether it
   actually covered a different period.

## The fix

1. **`ReportService._generate`'s vision branch** now runs
   `FinancialMetricsExtractor._extract_period_fields(reporting_period_text)` against Gemini's own
   period string — reusing the exact same "ended DD Month YYYY" + half-year/full-year cue regex the
   deterministic extractor already runs against full filing text, not a new implementation. "Financial
   year ended 30 June 2025" matches that pattern directly.
2. **New `_covers_same_period`/`_select_previous` in metrics.py**: `previous` now skips any candidate
   row whose `reporting_period_start`/`_end` exactly match the anchor's, falling back to the anchor's
   own embedded `_prior` field (here: `None`, since vision extraction doesn't provide one) rather than
   ever diffing two documents that describe the same period. Deliberately does not attempt to borrow a
   *different* document's `_prior` value to manufacture a comparison — that would blend two
   independently-extracted documents into one claimed figure, contradicting the "one document's own
   embedded prior column" principle used everywhere else in this project. An honest 0%/neutral beats a
   plausible-looking borrowed number.

## Verification performed

- `pytest tests/` — 216 passed (2 new: a vision extraction with a real "ended DD Month YYYY" period
  string correctly derives `reporting_period_start`/`_end`/`_end_prior`; a same-period-duplicate
  scenario correctly falls back to neutral instead of a fabricated "0% change").
- `npx tsc --noEmit` — clean (backend-only fix, frontend untouched).
- Diagnosed against real production data first (`curl` against the live Railway API), not a local
  reproduction guessed from the code alone — the exact `836991.0`/`836991.0` history duplicate
  confirmed the hypothesis before any line was changed.
- **Known caveat, documented rather than silently assumed away**: this fix only applies to a *fresh*
  extraction. ADF Farm Solutions' already-persisted row in production still has
  `reporting_period_start=None` baked in from before this deploy, and Railway's ephemeral filesystem
  means the original PDF likely won't survive the redeploy either — `regenerate` won't work on it. A
  delete + fresh re-upload is needed to actually observe the fix against that specific document in
  production.
