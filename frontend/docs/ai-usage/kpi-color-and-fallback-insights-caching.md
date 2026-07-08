# AI Usage — fix/kpi-color-and-fallback-insights-caching

## Context

All five fixes in this branch were reported directly from one real screenshot of the live dashboard,
sent right after PR #54's same-period-merge fix deployed. A reminder that shipping a fix surfaces the
next layer of real usage, not an end state -- none of these five were caught by the test suite, only
by actually looking at the deployed app.

## The five bugs

1. **AI Board Insights showing fallback content, refresh button disabled.** Confirmed by comparing the
   panel's rendered text word-for-word against `FALLBACK_INSIGHTS` in `lib/insights.ts` -- an exact
   match. Root cause: `getAiInsights` returned a bare `Insight[]`, so a fallback result (quota
   exhausted, no key, or a parse failure) got cached and gated the manual refresh button *identically*
   to a real successful generation. Once fallback was ever returned for a given metrics content, the
   button read "already up to date" forever, even though nothing real had ever been generated for it.
2. **EBITDA at -€613K in plain black text, not red.** `trend === 'neutral' ? 'text-foreground' :
   textClass` in both `KpiCard` and `KpiStatStrip` -- EBITDA has no prior-period comparative, so its
   trend is `neutral` (the "no data to compare" case), and neutral always fell back to plain text
   regardless of the value's own sign. `KpiStatStrip` even had a comment already describing the
   *intended* behavior ("a metric like EBITDA Margin at -133.5% shouldn't read in plain neutral
   text") without the code actually implementing it.
3. **Bare "N/A" for every missing metric.** No context on *what* was missing.
4. **The merged document's company name showing a raw filename on the Reports page.** Found by the
   user asking "how do we define reports" after noticing the merged FY2025 entry didn't read like a
   real company name the way the other two did.
5. **A dead-looking Download button after a 404.** A plain `<a href download>` navigation gives the
   browser nothing to show when the backend 404s (Railway's ephemeral filesystem).

## The fixes

1. New `isFallback: boolean` on the `/api/insights` response and `getAiInsights`'s return shape
   (`{ insights, isFallback }` instead of a bare array). `ai-insights.tsx` only calls
   `setCachedInsights` when `!isFallback` -- a fallback result still renders (nothing better to show),
   but never gets treated as "done" for that data. The server-side circuit breaker (rate-limit/billing
   backoff, already existing) still fully protects actual Gemini quota; this only changes the
   frontend's own bookkeeping of "do I already have something real."
2. New `getValueTextClass(trend, value)` in `lib/format.ts`, shared by both `KpiCard` and
   `KpiStatStrip` (previously each had its own copy of the same buggy ternary) -- a real trend still
   wins when one exists; a neutral trend falls back to checking whether the *formatted value string*
   itself starts with "-" (the backend's currency/percent formatters always prefix a negative value
   that way, confirmed against `MetricsService.format_currency`'s own docstring) and renders it in the
   same rose color as a real decline.
3. New `_MISSING_VALUE_MESSAGES` dict in `metrics.py`, applied via `build()`/`ratio_kpi()`/
   `bookings_kpi()`. Kept `_EMPTY_RATIO` (the "no eligible document exists at all" case) as a
   separate, deliberately generic "No data yet" -- there's no specific document to blame a missing
   field on in that case, so a field-specific message would be misleading.
4. `period_merge_service.py`'s `merge_documents` already *computed* a proper `company_name` fallback
   chain (prefer a real extracted name from either source's own Report over a raw filename) -- but the
   `Report(...)` construction underneath it still hardcoded `existing_doc.filename` directly, never
   actually using the computed variable. A real bug in the previous branch, not a new incident --
   caught while investigating the user's report, fixed by actually wiring the computed value through.
5. New `downloadDocument(documentId, filename)` in `data-service.ts` (fetch the file, on success
   trigger a real blob-based file save; on failure, throw with the backend's actual `detail` message,
   same convention as `uploadPDF`/`deleteDocument`) and a matching `useDownloadDocument` hook, replacing
   the plain anchor tag. Surfaces through the Documents page's existing error banner.

## Reuse audit

- `getValueTextClass` centralizes what was two separate, drifted copies of the same intended-but-
  unimplemented logic -- one shared function, not a third copy.
- `downloadDocument`/`useDownloadDocument` follow the exact same shape as every other mutation in
  `data-service.ts`/`use-mutations.ts` (`deleteDocument`/`useDeleteDocument`,
  `approveDocument`/`useApproveDocument`) -- same throw-on-failure convention, same
  `res.json().then(...).catch(() => null)` detail-parsing already established in `apiFetch`.
- The merged-report company-name fix reuses `Report.summary` (already queried) rather than adding any
  new field or query.

## Verification performed

- `pytest tests/` -- 223 passed (2 new: field-specific ratio-KPI messages when a real document is
  missing them vs. the generic "No data yet" when no document exists at all; the merged report's
  company name test also required extending `test_period_merge.py`'s `_FakeGemini` with a
  test-settable `company_name` to exercise both branches of the fallback chain).
- `npx vitest run` -- 176 passed (9 new: fallback insights don't disable refresh; `isFallback` is
  correctly set on both the success and failure paths of the `/api/insights` route;
  `getValueTextClass` unit tests for all three trend states plus the negative-neutral-value case;
  download success/failure/generic-fallback-message tests).
- `npx tsc --noEmit` / `next build` -- clean.
- Every bug traced to its exact root cause against the real screenshot/API responses before writing
  any fix, not guessed from the symptom alone (e.g. the company-name bug was confirmed by comparing
  the real production `/api/reports` response against what `merge_documents` was supposed to compute).
