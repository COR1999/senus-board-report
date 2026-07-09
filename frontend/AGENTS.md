# Senus Board Intelligence Platform — Agent Instructions

## Product context

Senus PLC is a natural capital SaaS company focused on environmental
measurement, reporting, and verification (MRV). Customers: governments,
corporates, farmers, financial institutions. This app is a board-level AI
financial intelligence dashboard for Senus's executives, board, and
investors — it should feel like **Bloomberg terminal meets Stripe dashboard
meets climate analytics platform**.

## Tech stack

- Next.js (App Router), React 19, TypeScript
- Tailwind CSS, shadcn/ui + Radix UI primitives
- Recharts for charts
- Gemini API for AI-generated insights (frontend, `app/api/insights/route.ts`);
  backend also uses Gemini separately for financial data extraction/analysis
  (`backend/app/services/gemini_service.py`) -- same provider, but independent
  integrations with independent API keys/quota, don't conflate them
- Backend: FastAPI + SQLAlchemy (see `backend/docs/frontend-api-routes.md`
  for the REST contract this frontend consumes)

## Design system

### Brief and references

The dashboard was explicitly redesigned (`feature/executive-dashboard-redesign`) to feel like a
premium boardroom tool a CEO/CFO would use in a live presentation, not an internal analyst tool —
references: Stripe Dashboard, Linear, Vercel, Bloomberg Terminal (simplified), McKinsey executive
decks. Working principles from that brief, still in force:

- Cards should feel like presentation slides, not app widgets.
- Typography is a primary design element, not just a delivery vehicle for numbers.
- Muted colors with one accent color for positive signal; bright color reserved for genuinely
  significant changes, not decoration.
- Generous whitespace and a strong hierarchy over dense, small-multiple widgets.
- Be opinionated: merge or cut a component rather than let screen space go to something that isn't
  earning it.

### Color

- **Dark institutional UI** (finance + climate intelligence), Bloomberg-terminal-adjacent.
- **Green (emerald)** = growth / nature / positive KPI movement — also Senus's own brand color
  (the sidebar logo mark is `bg-emerald-500`).
- **Blue** = AI / insights / system intelligence (the AI Board Insights header icon, "Opportunity"
  insight badges).
- **Sidebar is a fixed dark palette in *both* light and dark theme** — deliberately not
  theme-following. This was a direct fix for "light mode looks awful": the whole UI, including the
  branded sidebar, was washing out uniformly under the naive theme-follow approach. A dark, branded
  sidebar next to a theme-following content area is a common, intentional pattern (Stripe/Linear-
  style dashboards), not an inconsistency.
- **Real light/dark/system theme support** was added later (`next-themes`) — dark mode had
  previously been dead code: dozens of `dark:` Tailwind classes existed with nothing ever applying
  the `.dark` class they depended on.
- Semantic color (trend up/down/neutral, insight positive/risk/opportunity) is expressed as a
  fixed icon + label pairing, never color alone — accessibility requirement carried through every
  badge/pill in the dashboard.
- Watch for **token collisions**: `--secondary` and `--muted` were found to be the exact same color
  value in this theme, which made a `variant="secondary"` "active" state on a `bg-muted` track
  genuinely invisible, not just low-contrast. The fix (an elevated `bg-background`/`shadow-sm` pill)
  is the standard segmented-control pattern going forward for any tab-like control — confirm two
  tokens are actually visually distinct before relying on them for contrast, don't assume from the
  name alone.

### Typography & density

- Use shadcn/ui `Card`/`Badge`/etc. primitives and semantic Tailwind tokens (`text-foreground`,
  `text-muted-foreground`) over raw colors.
- Hero KPI text size was deliberately dialed back once (`text-4xl`/`text-5xl` → `text-3xl`/`text-4xl`,
  `space-y-10`/`p-10` → `space-y-6`/`p-8`) after the larger sizing made the page require zooming out
  to ~50% to view without scrolling — bigger is not automatically better for an executive-glance
  dashboard; legibility at 100% zoom takes priority.
- Table cell/head padding was increased (`p-2` → `px-3 py-3`) after direct "poor use of padding/
  margins" feedback — err toward more breathing room in tabular data, not less.
- Icon sizes were bumped roughly one Tailwind scale step across the whole dashboard (e.g. `h-4 w-4`
  → `h-5 w-5`) for legibility — including the shared `Badge` component's own default SVG size, since
  Badge forces its own icon size via `[&>svg]:size-*!` regardless of a child icon's own className.

### Layout patterns

- **KPI hierarchy, not one flat grid**: a 4-card hero row (large, presentation-slide styling) for
  the headline metrics, plus a compact secondary "stat strip" for the remaining assignment-required
  ratios — each of the assignment's 5 KPI categories stays visible, without competing for the same
  visual weight. The stat strip was later split into individually-boxed cards (was one shared card
  with internal columns) to read as more clearly separated.
- **Sidebar**: an icon-only rail by default, expanding to show labels on hover/keyboard-focus —
  pure CSS (`hover:w-64`/`focus-within:w-64` on a `fixed`/`overflow-hidden` element), not a
  click-to-toggle control with persisted state. The expanded state overlays page content rather
  than pushing/reflowing it.
- **Charts**: minimal gridlines (horizontal-only, low-opacity), no chart junk, one metric plotted
  at a time (a series-swap toggle, not a dual-axis overlay — KPIs are on very different scales and
  can have different signs). Projected/forecast data points get a distinct visual treatment
  (dashed line, indigo `#6366f1`, italic axis labels) so they never look like real historical data.
  A line chart is not the default presentation — `revenue-chart.tsx`'s `determineRenderMode` picks
  a stat callout, a bar comparison, or a line chart based on how many real points actually exist per
  cadence bucket (1 / 2 / 3+ respectively); a 1-2-dot "trend" communicates nothing real, so it isn't
  drawn as one. The forecast toggle only appears once a real trend exists to project from (line mode)
  — see `docs/dashboard-review.md`'s "Fixing the charts" section for the incident this replaced.
- **Single-user chrome, not multi-tenant chrome**: this is a boardroom presentation tool for one
  fixed presenter identity, not an account-management product — no login/logout, no editable
  profile, no notifications system. Don't add UI that implies otherwise (see `docs/roadmap.md`'s
  "single-user tidy-up" entry for what was actively removed and why).

## Development rules

1. **Work in feature-branch scope only.** Don't redesign architecture or
   implement unrelated features. Keep changes isolated and modular.
2. When making a nontrivial change, be ready to explain: file structure,
   code changes, component breakdown, and data flow.
3. Assume the backend API exists per `backend/docs/frontend-api-routes.md`.
   If an endpoint doesn't exist yet, mark the contract clearly rather than
   guessing at a shape.
4. Prioritize: clarity for executives (CFO/CEO-level UX), clean data
   visualization, the AI-insights layer, and reusable, performant components.
5. Use Tailwind + shadcn patterns consistently with the existing components.

## Current dashboard components

`components/dashboard/`, roughly in the order they appear on the executive
dashboard (`/`) -- see `docs/dashboard-review.md` for why this order and the
adaptive-visibility rules behind several of them:
- `dashboard-container.tsx` — top-level client component; fetches
  metrics/chart/reports/cost-waterfall data via `lib/hooks/` and composes
  the page. Data-shaping (which KPIs to show, which chart mode to render)
  is delegated to pure functions in `lib/` rather than done inline here.
- `kpi-card.tsx` / `kpi-sparkline.tsx` — hero KPI card (value, delta,
  trend, optional sparkline).
- `kpi-stat-strip.tsx` — the secondary "Financial Health" row. Which slots
  render comes from `lib/kpi-selection.ts`'s adaptive fallback cascade, not
  a fixed list — a category with nothing real to show is omitted, never
  rendered empty.
- `revenue-chart.tsx` — Revenue/EBITDA/Cash trend. Presentation (stat
  callout / bar comparison / line chart) follows real point count per
  cadence bucket, see `determineRenderMode`.
- `cost-waterfall-chart.tsx` — Revenue → … → EBITDA waterfall; renders
  nothing when the selected period's filing doesn't disclose a full cost
  breakdown.
- `growth-forecast-cards.tsx` — Method Two (guidance-based) forecast stat
  cards, see `lib/forecast.ts`.
- `ai-insights.tsx` — the closing "AI Board Insights" panel; composes
  `lib/hooks/use-ai-insights.ts` (per-report) and
  `lib/hooks/use-historical-trend-insight.ts` (all-reports trend) into one
  ranked feed rather than two separate cards.
- `recent-reports.tsx` — a short pointer to the latest few reports, linking
  to the full `/reports` page. `reports-table.tsx` is the full
  searchable/filterable/exportable table used there (and only there).
- `sidebar.tsx`, `top-nav.tsx` — navigation shell.

Shared logic lives in `lib/`: `data-service.ts` (API calls + types),
`format.ts` (trend/percent formatting), `kpi-selection.ts` (adaptive KPI
fallback cascade), `forecast.ts` (trend-based and guidance-based
projections), `mock-data.ts` (fallback data when the backend is
unreachable). Data-fetching hooks live in `lib/hooks/`
(`use-dashboard-data.ts`, `use-ai-insights.ts`,
`use-historical-trend-insight.ts`, `use-async-data.ts` as the shared
loading/error/data/refetch primitive underneath all of them).

Extend these existing components/utilities rather than replacing them
unless a change genuinely requires it.
