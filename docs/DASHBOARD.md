# Dashboard Architecture

> **Historical document.** Written during the project's initial manual-build phase (see
> `docs/roadmap.md`), before most of the current architecture existed — some of what's described
> below (e.g. the top-nav search box and notifications) was later removed as non-functional. Kept
> for history; see `docs/architecture.md` for the current, accurate system architecture.

## Overview
The Senus Board Intelligence Dashboard is an executive-level reporting platform that displays key business metrics, revenue trends, and recent reports in real-time.

## Purpose
Provide executives with a centralized view of:
- **KPI Metrics**: Revenue, customers, cash position, and EBITDA
- **Revenue Trends**: Visual chart showing monthly revenue progression
- **AI Insights**: AI-generated business intelligence and recommendations
- **Recent Reports**: Latest financial and board reports with download capabilities

## Architecture

### Component Structure
DashboardContainer (Smart Component)
├── Sidebar (Navigation)
├── TopNav (Header with search/notifications)
└── Main Content
├── KPI Cards (4x metrics)
├── Revenue Chart
├── AI Insights Panel
└── Reports Table

text

### Data Flow

1. **DashboardContainer** (entry point)
   - Fetches all data via `data-service`
   - Manages loading/error states
   - Passes data down to child components

2. **data-service.ts** (data layer)
   - `getMetrics()` → fetches KPI data
   - `getChartData()` → fetches revenue trends
   - `getReports()` → fetches reports list
   - Fallback to mock data if API unavailable

3. **Child Components** (presentational)
   - `KpiCard` - displays individual metrics
   - `RevenueChart` - renders Recharts line chart
   - `AiInsights` - displays insights
   - `ReportsTable` - displays reports with download buttons
   - `Sidebar` - displayed the sidebar
   - `TopNav` - top navigation


## Mock Data

Located in `lib/mock-data.ts`:

```typescript
mockMetrics: {
  revenue: { value: '€836,991', change: 38, trend: 'up' },
  customers: { value: '158', change: 2.5, trend: 'up' },
  cash: { value: '€1.2M', change: 15, trend: 'up' },
  ebitda: { value: '€150K', change: 22, trend: 'up' }
}

mockChartData: [{ month: 'Jan', revenue: 60000 }, ...]

mockReports: [{ id, name, date, status }, ...]
Testing Strategy
Test Files
dashboard-container.test.tsx - Tests the main dashboard container
kpi-card.test.tsx - Tests KPI card rendering
reports-table.test.tsx - Tests reports table
revenue-chart.test.tsx - Tests chart rendering
sidebar.test.tsx - Tests navigation
top-nav.test.tsx - Tests top navigation
Test Approach
Mocking Strategy:

Mock data-service functions to return mock data
Don't mock fetch - let tests use the data service layer
Tests verify component behavior, not implementation
Benefits:

✅ Tests use real data-service flow
✅ When API is added, tests automatically use real data
✅ No need to update tests after backend integration
✅ Data-driven tests scale with mock data changes
Example Test
typescript
it('renders KPI metrics from data-service', async () => {
  render(<DashboardContainer />)

  await waitFor(() => {
    expect(screen.getByText(mockMetrics.revenue.value)).toBeInTheDocument()
  })
})




