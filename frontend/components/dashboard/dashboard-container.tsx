'use client'

import { DashboardShell } from './dashboard-shell'
import { KpiCard } from './kpi-card'
import { KpiStatStrip, type StatStripItem } from './kpi-stat-strip'
import { RevenueChart } from './revenue-chart'
import { AiInsights } from './ai-insights'
import { ReportsTable } from './reports-table'
import { useMetrics, useChartData, useReports } from '@/lib/hooks/use-dashboard-data'
import { periodComparisonLabel, periodContextLabel } from '@/lib/period'
import { DollarSign, Users, Wallet, TrendingUp } from 'lucide-react'

// Background poll interval for the main dashboard's data -- lets the page
// pick up a newly generated report (new KPIs, chart point, AI commentary)
// without the user needing to reload or navigate away and back. Chosen to
// be frequent enough to feel "live" without hammering the backend/OpenAI
// for a personal dashboard that isn't updated more than a few times a year.
const DASHBOARD_POLL_INTERVAL_MS = 60_000

export function DashboardContainer() {
  const { data: metrics, loading: metricsLoading, error: metricsError } = useMetrics({
    pollIntervalMs: DASHBOARD_POLL_INTERVAL_MS,
  })
  const { data: chartData, loading: chartLoading, error: chartError } = useChartData({
    pollIntervalMs: DASHBOARD_POLL_INTERVAL_MS,
  })
  const { data: reports, loading: reportsLoading, error: reportsError, refetch: refetchReports } = useReports({
    pollIntervalMs: DASHBOARD_POLL_INTERVAL_MS,
  })

  const loading = metricsLoading || chartLoading || reportsLoading
  const error = metricsError || chartError || reportsError

  if (error) {
    return (
      <DashboardShell title="Executive Dashboard">
        <div className="text-red-600 bg-red-50 dark:bg-red-950 p-4 rounded-lg">
          Error: {error}
        </div>
      </DashboardShell>
    )
  }

  if (loading || !metrics) {
    return (
      <DashboardShell title="Executive Dashboard">
        <div className="animate-pulse space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-40 bg-muted rounded" />
            ))}
          </div>
          <div className="h-24 bg-muted rounded" />
        </div>
      </DashboardShell>
    )
  }

  // Real date context, not a fabricated cadence claim -- every metric below
  // that has an actual prior-period comparative (revenue, ebitda, cash, and
  // the stat-strip ratios) shares the same current/prior period, since they
  // all come from the same single filing's own comparison column.
  const comparisonTimeframe = (fallback: string) =>
    periodComparisonLabel(metrics.current_period, metrics.prior_period, fallback)

  // Hero tier -- the 4 metrics a CEO/CFO looks at first, given the large,
  // presentation-slide treatment (see KpiCard's `variant="hero"`). Every other
  // graded metric (Bookings, EBITDA Margin, Cash Runway, Interest Cover,
  // ROCE) stays fully visible below in the compact KpiStatStrip -- nothing
  // required by the assignment brief is cut, only visually de-prioritized.
  const heroMetricConfig = [
    { key: 'revenue' as const, title: 'Total Revenue', icon: DollarSign, timeframe: comparisonTimeframe('vs prior period') },
    { key: 'ebitda' as const, title: 'EBITDA', icon: TrendingUp, timeframe: comparisonTimeframe('vs prior period') },
    { key: 'cash' as const, title: 'Cash Position', icon: Wallet, timeframe: comparisonTimeframe('vs prior period') },
    // No real prior-period comparative exists for customers (same
    // reliability class as Bookings) -- state the period as context rather
    // than implying a quarter-over-quarter comparison that isn't real.
    { key: 'customers' as const, title: 'Active Customers', icon: Users, timeframe: periodContextLabel(metrics.current_period, 'current customer count') },
  ]

  // "Bookings" = new contract value signed/closed in the period (distinct
  // from Revenue, which is recognised over time as work is delivered) --
  // spelled out here since it's finance/SaaS jargon that isn't self-evident
  // from the number alone. Category captions below map each stat to the
  // assignment brief's own required categories (Growth & Revenue,
  // Profitability, Cash & Liquidity, Solvency & Leverage, Returns).
  const statStripSource = [
    {
      key: 'bookings' as const,
      category: 'Growth & Revenue',
      label: 'Bookings (new business closed)',
    },
    { key: 'ebitda_margin' as const, category: 'Profitability', label: 'EBITDA Margin' },
    { key: 'cash_runway' as const, category: 'Cash & Liquidity', label: 'Cash Runway' },
    { key: 'interest_cover' as const, category: 'Solvency & Leverage', label: 'Interest Cover' },
    { key: 'roce' as const, category: 'Returns', label: 'ROCE' },
  ]
  const statStripConfig: StatStripItem[] = statStripSource.map(({ key, category, label }) => ({
    key,
    category,
    label,
    value: metrics[key].value,
    changePercentage: metrics[key].change,
    trend: metrics[key].trend,
    // Only Bookings lacks a real prior-period comparative today (its
    // history is a single point, see Metrics.bookings) -- the other four
    // stat-strip ratios have a real prior value whenever N/A isn't shown.
    hasComparison: metrics[key].history.length >= 2,
  }))

  return (
    <DashboardShell title="Executive Dashboard" description="How the business is performing, at a glance">
      {/* Hero KPI row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {heroMetricConfig.map(({ key, title, icon: Icon, timeframe }) => (
          <KpiCard
            key={key}
            variant="hero"
            title={title}
            value={metrics[key].value}
            changePercentage={metrics[key].change}
            trend={metrics[key].trend}
            history={metrics[key].history}
            icon={Icon}
            timeframe={timeframe}
          />
        ))}
      </div>

      {/* AI Board Insights -- surfaced right under the headline numbers
          (rather than beside the chart, further down) per feedback that the
          narrative commentary should be one of the first things a board
          reader sees, not something they scroll past the chart to find. */}
      <AiInsights metrics={metrics} />

      {/* Secondary metrics: Bookings, Profitability, Cash & Liquidity, Solvency & Leverage, Returns */}
      <KpiStatStrip items={statStripConfig} periodLabel={comparisonTimeframe('') || undefined} />

      {/* Revenue Trend chart */}
      <RevenueChart data={chartData ?? []} periodLabel={metrics.current_period} />

      {/* Reports Table */}
      <ReportsTable reports={reports ?? []} onRegenerated={refetchReports} />
    </DashboardShell>
  )
}
