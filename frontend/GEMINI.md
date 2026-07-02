# Senus Board Intelligence Dashboard

## Project Overview
Building an AI-powered board reporting dashboard for Senus, a public environmental SaaS company.

## Tech Stack
- Frontend: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui (Radix + Geist)
- Backend: FastAPI (Python)
- Database: PostgreSQL
- AI: Google Gemini API
- Charts: Recharts
- Icons: Lucide React
- Deployment: Vercel (frontend) + Railway (backend)

## Current Phase
Sprint 2: Building the executive dashboard shell with mock data.

## Project Structure
frontend/
├── app/
│ ├── page.tsx (main dashboard)
│ ├── layout.tsx
│ └── globals.css
├── components/
│ ├── dashboard/
│ │ ├── sidebar.tsx
│ │ ├── top-nav.tsx
│ │ ├── kpi-card.tsx
│ │ ├── revenue-chart.tsx
│ │ ├── ai-insights.tsx
│ │ └── reports-table.tsx
│ └── ui/ (shadcn components)
├── lib/
│ ├── utils.ts
│ └── types.ts
├── data/
│ └── mock-data.ts
└── public/

## Key Metrics to Display
- Revenue (€836K)
- Customers (138)
- Cash Position
- EBITDA
- Revenue Growth (50% CAGR target)

## UI Design Principles
- Inspired by Stripe, Vercel, Linear
- Minimal, professional aesthetic
- Large whitespace
- Soft shadows
- Dark mode support
- Executive-focused (CEO, Board, Investors)
- No authentication required
- Mock data only (no backend yet)

## Component Requirements

### KPI Card
- Props: title, value, changePercentage, trend, icon
- Shows metric value with % change
- Color-coded trend (green up, red down)
- Uses shadcn Card component

### Sidebar
- Collapsible navigation
- Menu items: Dashboard, Reports, Documents, Settings
- Active state styling
- Lucide icons
- Responsive

### Top Navigation
- Logo/brand
- Search bar (optional)
- User avatar (mock)
- Notification icon (mock)

### Revenue Chart
- Line chart using Recharts
- 12-month data
- Responsive
- Interactive tooltips

### AI Insights Panel
- Card with insights about financial trends
- Mock AI-generated commentary
- Professional language

### Reports Table
- Recent reports list
- Columns: Date, Company, Status, Action
- Sortable (UI only, no backend)
- Professional styling

## Coding Standards
- Use TypeScript for all components
- Create reusable, composable components
- Use shadcn/ui Card, Button, Badge, Avatar, Table
- Tailwind CSS for styling
- Props validation with TypeScript interfaces
- No authentication logic
- Focus on UI/UX quality

## Git Commit Convention
- feature/[component-name]
- Small, meaningful commits
- Example: feat: add KPI card component

## Notes
- Do NOT add backend logic yet
- Do NOT connect to APIs
- Focus entirely on frontend architecture and visual design
- Make it look like a polished SaaS product