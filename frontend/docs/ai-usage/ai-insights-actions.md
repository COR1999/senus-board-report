# AI Usage — feature/ai-insights-actions

## What was built

User feedback: the AI Board Insights panel took up a lot of dashboard space
for 3-5 sentences that mostly restated the KPI cards above it. Two directions
were discussed (denser text per insight vs. a distinct recommended-action
field); the user picked the latter, and explicitly asked for it to tie into
other already-built features rather than stand alone.

1. **`action` field**: each `Insight` now carries a required `action: string`
   -- a concrete recommended next step for the board, distinct from the
   observation in `text`. `buildInsightsPrompt` (`lib/insights.ts`) asks for
   this explicitly, and fixes the count at exactly 3 insights (was "3-5") to
   offset the extra line's height -- net effect should be flat-to-lower total
   panel height with meaningfully more useful content per insight.
2. **`category` field, tied to the assignment's 5 KPI categories**: a new
   `lib/kpi-categories.ts` exports `KPI_CATEGORIES`/`KpiCategory` as the
   single source of truth for Growth & Revenue / Profitability / Cash &
   Liquidity / Solvency & Leverage / Returns -- previously these existed only
   as untyped inline strings in `dashboard-container.tsx`'s `statStripSource`
   (confirmed via exploration: `StatStripItem.category` was a loose `string`,
   the same 5 literals duplicated verbatim in that component's test fixture).
   `dashboard-container.tsx` and `kpi-stat-strip.tsx` now reference the shared
   constant/type instead. Each AI insight is optionally tagged with the most
   relevant category (omitted when an insight genuinely doesn't fit one), and
   `ai-insights.tsx` renders it with the exact caption styling `KpiStatStrip`
   already uses -- so an insight visually anchors to a KPI section that
   already exists on the same dashboard.
3. **Chart tie-in via the prompt, not code coupling**: `buildInsightsPrompt`
   also tells Gemini the Revenue Trend chart below has a Revenue/EBITDA/Cash
   toggle, so a recommended action can naturally say "view the EBITDA trend
   on the chart below" when relevant -- deliberately prompt-level only
   (`revenue-chart.tsx`'s `MetricKey`/`METRICS` stay module-local, not
   exported), no new component coupling for a purely textual reference.
4. **`parseInsightsResponse` tolerance**: a missing/non-string `action`
   defaults to `''` rather than sinking the whole insight (a slightly
   malformed model response still renders); an unrecognized `category`
   is dropped (insight still renders, just without a category caption).

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5). Went through EnterPlanMode before
implementing (multi-file, schema-shape change) -- the plan was reviewed and
approved by the user before any code was written.

## Notable decisions made along the way

- **Action as a genuinely separate field/line, not folded into `text`**: the
  user's own framing of the chosen option was "one line of 'so what' per
  insight" -- kept it visually distinct (small arrow icon, muted `text-xs`)
  rather than merging it into the observation sentence, at the cost of a
  small height increase per insight (offset by fixing the count at 3).
- **Category tagging reuses `KpiStatStrip`'s existing caption style exactly**:
  rather than inventing a new visual treatment, matching an established
  pattern keeps the dashboard's visual language consistent and makes the tie
  to an existing section immediately legible.
- **Extracted `KPI_CATEGORIES` as shared source of truth**: found the 5
  category strings were previously duplicated (once in
  `dashboard-container.tsx`, again in `kpi-stat-strip.test.tsx`) with no type
  enforcing them to stay in sync -- same "extract the repeated value" spirit
  as `feature/dashboard-code-quality`'s `current-user.ts`.
- **Chart reference stays prompt-only**: considered exporting `revenue-chart.tsx`'s
  `MetricKey`/`METRICS` so `AiInsights` could reference the exact toggle
  labels programmatically, but there's no actual interaction needed (the
  insight text just mentions the chart exists) -- exporting internals of one
  component for another to read, with no behavior depending on it, would be
  an abstraction the feature doesn't need.
- **`category` optional, `action` required**: not every insight cleanly maps
  to one of the 5 categories (e.g. a customer-growth or headcount
  observation), so forcing a category would produce misleading tags; the
  action, by contrast, is the entire point of this branch, so it's required
  (defaulted to `''` only as a parse-tolerance fallback, not a normal path).

## Verification performed

- `cd frontend && npx vitest run lib/__tests__/insights.test.ts` -- new
  tests added alongside the existing ones (this file already existed with
  coverage for the pre-existing `text`/`type` shape): prompt mentions the
  3-item count, the 5 categories, and the chart; `parseInsightsResponse`
  accepts a well-formed action/category response, defaults a missing action,
  drops an unrecognized category without rejecting the insight, and existing
  malformed-JSON/empty-array/unrecognized-type behavior is unchanged.
- `cd frontend && npx vitest run` -- full suite passes (109 tests), including
  updated `ai-insights.test.tsx` assertions that the category caption and
  action line render alongside the observation.
- `cd frontend && npx tsc --noEmit` -- no errors (category typing tightened
  end-to-end from `StatStripItem` through to `Insight`).
- `cd frontend && npx next build` -- succeeds.
