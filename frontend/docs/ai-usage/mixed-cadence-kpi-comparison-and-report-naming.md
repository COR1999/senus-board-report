# AI Usage — fix/mixed-cadence-kpi-comparison-and-report-naming

## Context

Found via the user actually using the live production app immediately after PR #42 merged and
importing the real Information Document -- four real, distinct bugs surfaced this way, none caught
by the (extensive) test suite added in PR #42, because none of the existing tests exercised "two
real documents with different reporting cadences, both auto-accepted, together."

## What was found and fixed

1. **The KPI cards' own change%/history still blended cadences, even though the revenue-trend chart
   didn't.** PR #42 fixed `/dashboard/revenue-trend`'s cadence blending but missed that
   `/dashboard/summary`'s `previous = rows[1]` and `history()` used the *same* unfiltered `rows` list.
   Live-confirmed: importing the 12-month Information Document (revenue €837K) while the 6-month
   half-year filing (revenue €355K) was still the second-most-recent row produced a "+135.9%" change
   badge -- comparing an annual total against a half-year total as if sequential, instead of the
   real, honest FY2025-vs-FY2024 comparison (+21.6%) the Information Document's own embedded
   `revenue_prior` provides. Fixed with the same cadence-filtering approach already used for
   revenue-trend, applied to `rows` right after fetching, before `previous`/`history` are derived
   from it.
2. **Reports showed "Document #13" instead of a real name.** `_generate`'s Gemini-path branch (taken
   whenever the deterministic baseline is incomplete -- exactly the Information Document's case,
   since its EBITDA is genuinely undisclosed) had no fallback for a missing `company_name`; only the
   baseline-complete branch did. Fixed by falling back to the document's filename whenever neither
   Gemini nor the baseline produced one, applied uniformly regardless of which path was taken.
3. **`importExternalFiling` (and every other `apiFetch`-based call) showed a raw "422 Unprocessable
   Entity" instead of the backend's actual rejection reason.** Only `uploadPDF` had its own bespoke
   detail-parsing; the shared `apiFetch` helper never read `detail` from a FastAPI error body. Fixed
   in `apiFetch` itself (not re-duplicated per caller), so every current and future caller gets the
   real message -- confirmed this surfaced confusingly when the user tried importing a governance
   document (correctly rejected by the PR #42 confidence gate) and only saw the generic status code.
4. **A deeper root cause behind "AI Board Insights didn't update": `buildInsightsPrompt` iterated
   every key in `Metrics`, not just the real KPI cards.** `current_period`/`prior_period`/
   `data_extracted_at` are plain `string | null` fields on the same interface, not `MetricValue`s --
   `Object.entries(metrics).map(([key, m]) => ... m.value ...)` read `.value`/`.change`/`.trend` off
   a plain string (silently producing "undefined" garbage lines) or off `null` (throwing outright).
   Confirmed live: the deployed `/api/insights` endpoint returned HTTP 200 with the *exact* hardcoded
   `FALLBACK_INSIGHTS` text even when POSTed genuinely different metrics -- proving the prompt-builder
   itself was failing inside the route's try/catch, not a caching bug as first suspected. Fixed with a
   runtime `isMetricValue` type guard, robust against any future non-KPI field being added to
   `Metrics` without needing to keep an explicit key list in sync (this bug already existed for
   `current_period`/`prior_period` before this session; adding `data_extracted_at` in PR #42 made it
   worse, not better).
5. **Concurrent imports could race.** `useImportExternalFiling` tracks a single `importingId`, but
   the Import buttons only disabled the specific row being imported, not every row -- triggering a
   second import before the first resolved let one request's result silently overwrite the other's.
   Fixed by disabling every Import button whenever any import is in flight, per direct user
   suggestion.

Also folded a set of detailed user notes on HY/FY reporting-dashboard conventions into
`docs/roadmap.md` as a scoped future idea (a real period selector, not just "latest by extraction
time," with combined bare-label + calendar-range option text) -- explicitly separating the parts that
fit this project's real data (no budget figures, no monthly granularity, no segment breakdown exist
in any source filing) from the parts of a generic dashboard template that don't.

## Verification performed

- `pytest tests/` -- 169 passed (2 new: the mixed-cadence KPI regression test, the company_name
  fallback test).
- `npx vitest run` -- 131 passed (2 new: the insights-prompt garbage-field exclusion test, the
  null-safety test).
- `npx tsc --noEmit` -- no errors.
- `npx next build` -- succeeds.
- Root-caused "AI Insights didn't update" by directly POSTing genuinely different metrics to the
  live deployed `/api/insights` endpoint and observing it return the exact hardcoded fallback text --
  confirming the prompt-builder crash theory empirically rather than guessing.
