# AI Usage — feature/reports-documents-settings-polish

## What was built

Started as the planned "flesh out Reports/Documents/Settings" branch, but
grew substantially from the user live-testing the previous
`feature/executive-dashboard-redesign` branch on their own phone/desktop
throughout this session and reporting real bugs/legibility issues as they
found them. Both threads are covered here since they landed in the same
branch.

**Reports / Documents / Settings (the original scope):**
- Documents page: added real filename search (parity with Reports), a
  "Size" column using the `file_size` field the API already returned but
  the UI never rendered, and status-badge capitalization + color-coding
  (was rendering the raw lowercase API string in a flat neutral badge).
- Both Reports and Documents got a disabled "Filter by period" control
  (`title="Filter by year/month coming soon"`) matching the exact existing
  "PDF export coming later" disabled-button convention already in this
  codebase, per the user's request to note that year/month filtering is
  planned but not yet built.
- Settings: added a real, working "Appearance" section with a Light/Dark/
  System theme toggle, via `next-themes` + a new `ThemeProvider`. This
  wasn't cosmetic scope-padding -- investigating revealed dark mode was
  **completely dead code**: dozens of `dark:` Tailwind classes exist
  throughout the app, but nothing ever applied the `.dark` class
  `globals.css`'s `@custom-variant dark` selector expects, and there was no
  `prefers-color-scheme` fallback either. This activates all of that
  previously-inert styling for the first time.
- Replaced the Reports status filter's native `<select>` with a proper
  `components/ui/select.tsx` (new, built on `radix-ui`'s `Select`
  primitive, matching this codebase's existing shadcn-style wrapper
  pattern) -- native selects have inconsistent, hard-to-style browser
  chrome; this was flagged directly by the user as needing improvement.

**Dashboard fixes from live user testing (grew the branch considerably):**
- **Real date context**: KPI subtitles like "vs last quarter" were
  hardcoded UI copy with no real data behind them (`customers` has no
  prior-period comparative in this system at all). Added deterministic
  `reporting_period`/`reporting_period_prior` extraction to
  `FinancialMetricsExtractor` (the filing's own text -- "(HY2026)" for the
  current period, the recurring "(HY25:" comparison label for the prior),
  new `current_period`/`prior_period` fields on the summary response, and
  `lib/period.ts` building real subtitle text from them.
  - The 2-digit prior year ("HY25") was later normalized to 4 digits
    ("HY2025") after the user pointed out "HY25 vs HY2026" read as
    inconsistent side by side.
- **Revenue trend chart, several real bugs found via live testing**:
  - The chart's period label came from `extracted_at` (when the document
    was *processed*), not the period the filing actually covers --
    replaced with the same deterministic `reporting_period` field.
  - The chart only ever plotted one point per uploaded document, so with
    only one real document it showed a flat line despite the KPI card
    correctly showing "+4.1% vs prior period" -- the user asked directly
    whether that percentage was fabricated. It wasn't: the card's delta
    already came from the filing's own embedded `revenue_prior` value,
    which the chart just never plotted. Fixed by prepending that same
    value as the chart's first point when there's no second real document.
  - Rebuilt as a gradient-filled `AreaChart` (was a plain `LineChart`),
    with round Y-axis ticks, a completely custom tooltip (see below), and
    `accessibilityLayer={false}` to remove an ugly keyboard-focus outline
    box that appeared on click (same fix applied to `KpiSparkline`, which
    had the identical issue).
  - The default Recharts tooltip rendered one row per *series* even when
    that series had no real value at the hovered point -- hovering the
    oldest real point showed a spurious "Forecast" entry. A custom
    `RevenueTooltip` component filters to entries with a real value, and
    additionally drops a redundant "Forecast" entry when it exactly
    matches the "Revenue" entry already shown (the one point where the
    real and forecast series share a value by construction, to join the
    two lines visually).
  - The forecast toggle's projected points were labeled "+1"/"+2"/"+3" --
    read like leftover debug notation, especially once periods became
    "HY2026" rather than "Jan"/"Feb". Changed to "Projected N", which is
    also more honest about not knowing the real future period label.
  - The tooltip box rendered directly on top of the hovered point,
    obscuring it; increased Recharts' default 10px cursor offset to 24px.
- **Color signal**: every KPI's big value number and the stat-strip values
  were the same neutral color regardless of whether the metric was a
  strong gain or a widening loss -- "lack of colours to make certain
  metrics stand out" was direct user feedback. Colored both the value text
  and (after the user shared a reference design image) added back a
  trend-colored icon badge on `KpiCard` (previously removed for hero cards
  in the redesign branch in favor of pure typography -- the user's
  reference showed colored icon badges are actually part of what worked,
  so both signals now coexist).
- **Density**: the user reported having to zoom out to 50% to see the
  whole dashboard. The redesign branch's oversized hero value text
  (`text-4xl`/`text-5xl`) and generous shell spacing (`space-y-10`/`p-10`)
  were the main contributors -- dialed back to `text-3xl`/`text-4xl` and
  `space-y-6`/`p-8` respectively (bold weight carries the emphasis
  instead of sheer size, per the user's own suggestion).
- **Sidebar stays dark in both themes**: per the user's reference image,
  changed `sidebar.tsx` from theme-following (`bg-card`, `dark:` variants)
  to a fixed dark palette regardless of light/dark mode -- a dark, branded
  sidebar next to a light content area is a deliberate, common pattern
  (Stripe/Linear-style dashboards), and was likely part of why "light mode
  looks awful" was reported: the *whole* UI, including the sidebar,
  washing out to light gray lost the branded contrast dark mode
  coincidentally preserved.
- **Top nav layout bug**: `TopNav` never had `main`'s `md:ml-64` offset, so
  it rendered starting from behind the fixed-position sidebar instead of
  to its right -- this is what made its (also non-functional, never wired
  to a handler) search box look like a stray floating element clipped by
  the sidebar in a screenshot the user shared. Fixed the offset and
  removed the dead search box outright (Reports/Documents now have their
  own real search).
- **Header legibility**: `CardTitle` (shared by every card's header --
  "Revenue Trend", "Recent Reports", etc.) went from `font-medium` to
  `font-semibold` with explicit `text-foreground`, the stat-strip's
  category captions from a barely-legible `text-[11px]` at reduced
  opacity to `text-xs font-semibold` at full contrast, and the main page
  `<h1>` back up to `text-3xl` after the density pass had shrunk it --
  all per direct "headers are hard to read" feedback.
- **Table density**: `TableHead`/`TableCell` padding increased from a
  fairly tight `p-2` to `px-3 py-3`/`h-11 px-3`, and the filter-row margin
  above Reports/Documents tables increased, after direct "haven't made
  good use of padding/margins" feedback.
- **Select trigger text-wrap bug**: the new status-filter `Select`'s
  trigger had `w-fit` with no `whitespace-nowrap`, so "All statuses" wrapped
  onto two lines inside a now-too-narrow box -- a real bug caught from a
  screenshot, fixed with `whitespace-nowrap` + a touch more padding.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). The
dashboard-fix portion was driven turn-by-turn by the user's own live
testing -- screenshots of real bugs (the floating top-nav search box, the
Select text-wrap, the tooltip showing a forecast value on a historical
point, the "HY25 vs HY2026" inconsistency) and a reference design image
they found and liked parts of. Several judgment calls were made explicitly
per the user's direction rather than by default: keeping *both*
trend-colored value text and colored icon badges (after an initial
instinct to pick one over the other based on the reference image, the
user said to keep both), and prioritizing "think about it, don't build
yet" for two open suggestions (plotting additional metrics on the revenue
chart; a toggle to compare metrics) -- see below.

## Notable decisions made along the way

- **`next-themes` added as a new dependency** rather than hand-rolling
  theme persistence -- it's the standard, SSR-safe solution purpose-built
  for exactly this (Next.js App Router dark mode), and `attribute="class"`
  matches `globals.css`'s existing `.dark`-class selector with no other
  changes needed.
- **The mounted-flag pattern in `ThemeToggle`** (`useEffect(() =>
  setMounted(true), [])`) trips this repo's `react-hooks/set-state-in-effect`
  lint rule, but is the standard, necessary way to avoid an SSR/client
  hydration mismatch (next-themes' own docs recommend it) -- explicitly
  suppressed with a comment explaining why, rather than contorted into a
  worse shape to satisfy the linter.
- **jsdom is missing `scrollIntoView`/pointer-capture APIs** that Radix
  UI's `Select` calls internally -- added no-op polyfills to the shared
  `test/setup.ts` (affects any future Radix popover-based component under
  test, not just this one).
- **Didn't build the "plot other metrics on the chart" or "toggle to
  compare metrics" ideas** the user raised -- both were explicitly framed
  as suggestions ("not sure what's the best data... think about the best
  approach"), not build requests. Worth surfacing back to the user rather
  than guessing: candidates are EBITDA/Cash (both already have `history`
  data flowing through the KPI cards), but combining differently-scaled
  metrics on one chart risks the dual-axis anti-pattern this project's
  dataviz conventions explicitly rule out -- small multiples or an
  indexed-to-100 view would be the safer pattern, and this is only worth
  building once there are more than 2 real data points to plot.
- **Didn't implement a real backend-driven period filter** for
  Reports/Documents -- the disabled "coming soon" button matches the
  user's own request (a note, not a full feature) and the existing
  codebase convention for exactly this situation.

## Verification performed

- `cd backend && pytest tests/` -- 90 passed, including the updated
  reporting-period digit-normalization assertions.
- `cd frontend && npx vitest run` -- 96 passed (added: theme toggle,
  Documents search/size/status/filter-button, Reports status-badge
  capitalization + filter-button + Select-based status filtering, KPI
  card/stat-strip trend-color assertions); `npx tsc --noEmit` -- no errors;
  `npx eslint .` -- clean on every file this branch touched (2
  pre-existing, unrelated issues remain elsewhere); `npx next build` --
  production build succeeds.
- **Manually verified end-to-end against the real production database**
  after the reporting-period digit fix: regenerated the real report,
  confirmed `current_period: "HY2026"`, `prior_period: "HY2025"` (4-digit,
  not the earlier "HY25"), and the revenue-trend endpoint returning both
  real points with consistent 4-digit year labels.
- Real OpenAI call not verified end-to-end this session (this branch
  didn't touch the AI Insights integration itself).
- The user did their own live visual verification throughout this branch
  on both desktop and phone, in both light and dark mode, which is what
  surfaced every bug fixed above -- this branch has had more real,
  in-browser testing than most before it, specifically because of that.
