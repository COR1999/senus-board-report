# AI Usage — fix/fabricated-zero-metrics-shadowing-latest

## What happened

A real production incident, not a hypothetical: after merging the investor-relations filing sync
feature, the user imported all 6 newly-available filings (AGM notices, a Memorandum & Articles of
Association, a standalone balance sheet, the Information Document, the ADF Farm Solutions
statements) into the live production database. The dashboard immediately went blank -- revenue,
cash, and EBITDA all showed "€0", and customers showed a plainly wrong "100".

## Root cause

Two compounding bugs, both pre-existing but only ever exercised now that more than one document
could go through the pipeline:

1. **`ReportService._save_metrics`'s `_normalize_metric`/`_extract_metric_value` helpers defaulted
   a genuinely missing value to `0` instead of `None`**, for exactly the four "baseline" fields
   (revenue, customers, cash, ebitda) -- every other field on the same model (the `_prior` fields,
   bookings, reporting period) already correctly used `_plain_metric_value`, which preserves `None`.
   This directly contradicted the project's own actively-defended "missing data is `null`, never a
   fabricated `0`" rule -- it just never surfaced before because the only document ever ingested
   (the half-year filing) always had real figures for all four fields.
2. **`GET /metrics/dashboard/summary` picked the single most-recently-extracted `FinancialMetrics`
   row as "current"**, with no regard for whether that row actually contained anything. A
   non-financial document's all-zero (post-bug-1) row was more recent than the real half-year
   filing's, so it silently became "the" dashboard data.

## Fix

- `report_service.py`: `_normalize_metric`/`_extract_metric_value` now preserve `None` for a
  genuinely missing value, matching every other field's existing convention.
- `metrics.py`: added `_HAS_CORE_METRICS` (at least one of the four baseline fields is non-null) as
  a `WHERE` filter on `/dashboard/summary`'s query -- a document with zero extracted signal can
  never be selected as "latest" again. Deliberately **not** applied to `/dashboard/revenue-trend`,
  which plots every document's data independently per field and has an existing test
  (`test_revenue_trend_preserves_null_for_missing_revenue`) asserting that a document missing one
  field still contributes a real (partially-null) point to the chart -- excluding it there would
  have contradicted that established, correct behavior.
- `metrics.py`'s `build()` helper and the "zero rows" empty-state branch now render `"N/A"` for a
  missing baseline KPI instead of calling the currency formatter on `None` (which itself defaults
  to `"€0"`) -- defense in depth, in case a future document has some but not all fields missing.
- `frontend/app/documents/page.tsx`: fixed a real JSX whitespace bug in the new-filings banner's
  title (`"filingsavailable"` instead of `"filings available"`), caused by splitting a single JSX
  text run across two source lines right after the pluralization expression -- JSX's whitespace
  collapsing trims the leading space in that situation. Replaced with a single template-literal
  expression, which is immune to source line-wrapping entirely.

## Immediate production cleanup

Before the code fix was even written, the 6 bad documents were deleted directly from the live
production database via `DELETE /api/documents/{id}` (confirmed with the user first, given this
project's standing rule about the live Railway DB not being a disposable local one) to restore the
dashboard immediately. The two real financial documents (Information Document, ADF Farm Solutions
statements) were deliberately left out for now, since neither is wired into
`financial_metrics_extractor.py` yet -- re-importing them today would reproduce the same all-null
row, just without the pre-fix's fabricated zero.

## Verification performed

- `pytest tests/` -- 136 passed (8 new: 5 in `test_report_service_save_metrics.py` covering
  `_save_metrics`/`_normalize_metric`/`_extract_metric_value`'s None-preservation directly, 3 in
  `test_metrics_summary.py` covering the "latest" selection skipping an all-null row, the
  all-null-rows-render-N/A empty state, and confirming a row with *some* (not all) fields missing
  is still correctly selected as latest).
- `npx vitest run` -- 125 passed.
- Confirmed against the real production API: deleted the 6 bad documents, re-fetched
  `/metrics/dashboard/summary`, confirmed the real half-year data (revenue €355K, 4.1% change,
  138 customers) was showing again before any code fix was deployed.
