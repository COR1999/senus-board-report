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
- OpenAI API for AI-generated insights (frontend); backend also uses Gemini
  separately for financial data extraction/analysis -- these are independent
  integrations, don't conflate them
- Backend: FastAPI + SQLAlchemy (see `backend/docs/frontend-api-routes.md`
  for the REST contract this frontend consumes)

## Design system

- Dark institutional UI (finance + climate intelligence)
- Green (emerald) = growth / nature / positive KPI movement
- Blue = AI / insights / system intelligence
- Minimal noise, high information density, board-level clarity
- Use shadcn/ui `Card`/`Badge`/etc. primitives and semantic Tailwind tokens
  (`text-foreground`, `text-muted-foreground`) over raw colors

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

`components/dashboard/`:
- `dashboard-container.tsx` — top-level client component, fetches metrics/
  chart/report data and composes the page
- `kpi-card.tsx` — KPI card (value, delta, trend, optional sparkline)
- `kpi-sparkline.tsx` — minimal inline Recharts chart used by `kpi-card.tsx`
- `revenue-chart.tsx` — full revenue trend chart
- `ai-insights.tsx` — AI-generated executive commentary panel
- `reports-table.tsx` — recent reports list
- `sidebar.tsx`, `top-nav.tsx` — navigation shell

Shared logic lives in `lib/`: `data-service.ts` (API calls + types),
`format.ts` (trend/percent formatting), `metrics.ts` (delta calculations),
`mock-data.ts` (fallback data when the backend is unreachable).

Extend these existing components/utilities rather than replacing them
unless a change genuinely requires it.
