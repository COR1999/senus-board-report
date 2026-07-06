# AI Usage — feature/executive-dashboard-redesign

## What was built

Implements the user's "premium boardroom dashboard" design brief (saved
verbatim in this session's memory) for the main dashboard page, plus
several real, data-accuracy fixes the user raised while reviewing this
branch on their phone partway through.

**Visual redesign (the original plan):**
- Removed the "Revenue by Segment" chart entirely -- it was permanently
  mock/fabricated data (no real segment split exists anywhere in the
  filing, confirmed earlier this session), and showing invented numbers on
  a "confidence and trust" boardroom dashboard contradicted the brief's own
  logic. Deleted the component, its test, `getSegmentBreakdown()`,
  `useSegments()`, `SegmentValue`, and `mockSegments` rather than leaving
  dead code.
- Split the 9 KPI cards into a **hero tier** (Revenue, EBITDA, Cash
  Position, Active Customers -- large, presentation-slide-style
  `KpiCard`s with a new `variant="hero"`) and a **compact secondary
  stat-strip** (`KpiStatStrip`: Bookings, EBITDA Margin, Cash Runway,
  Interest Cover, ROCE), so every assignment-required metric category stays
  fully visible without competing for visual weight with the metrics a
  CEO/CFO looks at first.
- Toned down the revenue chart's gridlines (horizontal-only, recessive
  stroke) and legend (only shown when the forecast series is on), per the
  brief's "minimal gridlines, no chart junk" rule.
- Light typography/spacing polish on `dashboard-shell.tsx`, `sidebar.tsx`,
  `top-nav.tsx` -- no functional changes there.

**Real date-context fixes (added mid-branch after user feedback):**
The user pointed out KPI subtitles like "vs last quarter"/"vs last month"
didn't say *which* quarter/month, and asked for real year/period context.
Investigating this surfaced two real, pre-existing inaccuracies:
- Those subtitles were **hardcoded UI copy with no real data behind them**
  -- `customers`, for instance, has no prior-period comparative in this
  system at all (confirmed: no `customers_prior` column), so "vs last
  quarter" was actively fabricated, not just imprecise.
- The revenue trend chart's X-axis label came from `extracted_at`
  (`strftime("%b %Y")`) -- **when the document was processed**, not the
  period the filing actually covers. Verified directly against the real
  database: the one real filing's `extracted_at` reflects its upload date,
  completely unrelated to the half-year period it reports on.

Fixed both by adding real reporting-period extraction:
- `FinancialMetricsExtractor` now extracts the filing's own period labels
  directly from its text -- `"(HY2026)"` for the current period and the
  recurring `"(HY25:"` comparison-column label for the prior period --
  stored verbatim as `reporting_period`/`reporting_period_prior` on
  `FinancialMetrics` (new columns + migration entries, same
  `_add_missing_columns` pattern as every other field added this session).
- `GET /metrics/dashboard/summary` now returns `current_period`/
  `prior_period`, and `GET /metrics/dashboard/revenue-trend` prefers the
  real period label over `extracted_at`. Both fall back, in order: the
  deterministic extractor's field -> an AI-extracted `Report.summary`
  field (present in the schema already, but populated by a Gemini path
  that's normally skipped once baseline extraction is complete, so usually
  empty in practice) -> a best-effort derived label
  (`MetricsService.derive_prior_period`, e.g. "H1 2025" -> "H1 2024") ->
  a generic, honest fallback string. Never a guessed label presented as real.
- Frontend: `lib/period.ts` (`periodComparisonLabel`, `periodContextLabel`)
  builds real subtitle text from these fields -- "H1 2024 vs H1 2025" style
  for metrics with a genuine prior comparative, "as of H1 2025" for
  `customers` (no real comparative exists, so no comparison is implied).
- Revenue chart Y-axis now formats ticks as "€250K"/"€1.2M" instead of raw
  numbers, and shows the real period as a `CardDescription` under the title.
- `KpiStatStrip`'s phone-width grid changed from 2 columns to 1 -- 5 items
  in 2 columns left an orphaned cell on the last row.

**Revenue trend chart showing a flat line despite a real +4.1% (added after
the user spotted it live and asked whether the delta was fabricated):**
The Total Revenue hero card correctly showed "+4.1% vs prior period" with a
sparkline sloping upward, but the big Revenue Trend chart below it rendered
a single flat point. The 4.1% was never fabricated -- it's the filing's own
real number (€340.9K -> €354.8K) -- but `GET /metrics/dashboard/revenue-trend`
only ever mapped existing `FinancialMetrics` *rows* to chart points, one row
per uploaded document. With only one document, that's one point, even
though that same row also stores the filing's own embedded prior-period
comparative (`revenue_prior`) -- the exact value the KPI card's percentage
and sparkline already use. Fixed by prepending that embedded prior value
(with its real period label, e.g. "HY25") as the chart's first point
whenever there's no second real document to plot against -- the same
"prepend embedded prior when len(rows) < 2" pattern the summary endpoint's
`history()` helper already used, just not previously applied here too.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). The hero/
secondary tiering split and the segment-breakdown removal were each
confirmed with the user via explicit questions before implementation
(recommended options chosen both times). The date-context work was
initiated entirely from the user's own mid-branch feedback -- they gave
"full control" to proceed without further check-ins, so the investigation
into *why* the periods were wrong, and the resulting extractor/schema/route
changes, were carried out and verified end-to-end without further pauses
for approval.

## Notable decisions made along the way

- **Real period labels kept verbatim, not normalized**: the filing calls
  its current period "HY2026" and its prior comparative "HY25" -- an
  inconsistent, idiosyncratic convention. An earlier, simpler design
  considered deriving the prior label mathematically from the current one
  (decrement the year in "H1 2025" -> "H1 2024"), but verified against the
  real filing text that this would produce the wrong string ("HY2025"
  instead of the filing's actual "HY25"). Extracting both labels directly
  from the text, rather than deriving one from the other, avoids
  fabricating a plausible-looking but wrong period.
- **Three-level fallback chain, never a guess presented as fact**:
  deterministic extraction -> AI extraction -> generic honest fallback text
  ("vs prior period"/"current customer count"). Verified each level
  independently with dedicated tests, including the case where the
  deterministic and AI-extracted values disagree (deterministic wins).
- **`customers` no longer claims a period comparison it doesn't have**:
  previously showed "vs last quarter", implying a real quarter-over-quarter
  delta existed. Since there's no `customers_prior` column and (today) only
  one document has ever been uploaded, that comparison was never real.
  Changed to a neutral "as of {period}" context string instead.
- **`next lint`'s `react-hooks/set-state-in-effect` caught a real issue
  early** (from the prior `feature/api-integration-layer` branch, reused
  here): synchronous `setState` calls at the top of a `useEffect` body are
  a cascading-render risk; fixed by moving the reset into the `refetch()`
  callback instead. Re-confirmed clean here since this branch touches the
  same hooks indirectly via `dashboard-container.tsx`.

## Verification performed

- `cd backend && pytest tests/` -- 90 passed, including new tests for the
  reporting-period extraction (against both synthetic text and the real
  uploaded PDF), the fallback priority chain, `derive_prior_period`, and
  the revenue-trend prior-point prepend (both the single-document case and
  a regression guard that it does *not* fire once a real second document
  exists).
- `cd frontend && npx vitest run` -- 85 passed; `npx tsc --noEmit` -- no
  errors; `npx eslint .` -- clean on every file this branch touched (2
  pre-existing, unrelated issues remain elsewhere, unchanged by this
  branch); `npx next build` -- production build succeeds.
- **Manually verified end-to-end against the real production database**
  (twice -- once before the revenue-trend prior-point fix, once after):
  restarted the backend locally (pointed at the real Railway Postgres, with
  standing permission to do so), confirmed the migration added
  `financial_metrics.reporting_period`/`reporting_period_prior` via startup
  logs, regenerated the one real report, and confirmed both endpoints
  return the real values: `current_period: "HY2026"`, `prior_period:
  "HY25"`, and the revenue-trend chart returning both real points --
  `{"period": "HY25", "revenue": 340931.0}` then `{"period": "HY2026",
  "revenue": 354813.0}` -- matching the +4.1% already shown on the card.
- Real OpenAI call not verified end-to-end this session (this branch
  didn't touch the AI Insights integration itself, only its container
  layout).
- Visual check of the redesigned layout (hero row sizing, stat-strip
  legibility, chart grid tone-down, dark-mode contrast, phone-width
  spacing) not available in this environment -- happy to walk through it
  live if you open a localhost for me to test against, as with prior
  branches.
