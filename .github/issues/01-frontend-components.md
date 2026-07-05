# Frontend Components Implementation

## Priority: 🔴 HIGH (Blocker)
## Estimated Time: 2-3 hours

## Overview
The frontend dashboard structure exists but component implementations are missing. This is blocking the delivery as the UI is currently showing skeleton/mock data only.

## Components to Implement

### 1. KpiCard Component
- [ ] Display financial metric value (formatted currency/number)
- [ ] Show change percentage with color coding (green for up, red for down)
- [ ] Render trend indicator (up/down/neutral)
- [ ] Display icon and timeframe label
- [ ] Responsive sizing

**File:** `frontend/components/dashboard/kpi-card.tsx`

**Example mock:**
```tsx
export function KpiCard({ 
  title, 
  value, 
  changePercentage, 
  trend, 
  icon: Icon, 
  timeframe 
}) {
  const isPositive = trend === 'up'
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold">{value}</p>
          <p className={`text-xs ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {isPositive ? '+' : ''}{changePercentage}% {timeframe}
          </p>
        </div>
        <Icon className="w-8 h-8 text-muted-foreground" />
      </div>
    </div>
  )
}
```

### 2. RevenueChart Component
- [ ] Render line/bar chart using Recharts
- [ ] Support YoY (Year-over-Year) comparison
- [ ] Support MoM (Month-over-Month) comparison
- [ ] Show tooltips on hover
- [ ] Responsive and mobile-friendly

**File:** `frontend/components/dashboard/revenue-chart.tsx`

**Requirements:**
- Accept chart data array: `{ month: string, revenue: number }[]`
- Add toggle buttons for YoY/MoM view
- Legend showing data sources

### 3. AiInsights Component
- [ ] Display AI-generated commentary and key findings
- [ ] Show loading state while fetching
- [ ] Handle error states gracefully
- [ ] Format key findings as bullet points
- [ ] Include metadata (generated_at, model version if available)

**File:** `frontend/components/dashboard/ai-insights.tsx`

### 4. ReportsTable Component
- [ ] Display list of uploaded documents/reports
- [ ] Show report status (completed, pending, processing, failed)
- [ ] Display report date and filename
- [ ] Add action buttons (view, regenerate, delete)
- [ ] Pagination support (limit 20 per page)
- [ ] Loading state and empty state

**File:** `frontend/components/dashboard/reports-table.tsx`

### 5. Document Upload Component
- [ ] Drag-and-drop PDF upload interface
- [ ] File validation (PDF only, max size)
- [ ] Upload progress indicator
- [ ] Success/error messaging
- [ ] Auto-refresh dashboard after successful upload

**File:** `frontend/components/document-upload.tsx`

### 6. Sidebar Navigation
- [ ] Dashboard link
- [ ] Documents/Reports link
- [ ] Settings link
- [ ] Active state indicator
- [ ] Collapsible on mobile

**File:** `frontend/components/dashboard/sidebar.tsx`

## Related Issues
- #4 API Integration

## Testing
- [ ] Visual regression tests
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Accessibility (WCAG 2.1 AA)

## Notes
- Use existing shadcn/ui components where possible
- Follow tailwindcss styling from existing theme
- Ensure loading and error states are present
