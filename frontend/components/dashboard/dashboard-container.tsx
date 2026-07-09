'use client'

import { useState } from 'react'
import { DashboardShell } from './dashboard-shell'
import { KpiCard } from './kpi-card'
import { KpiStatStrip, type StatStripItem } from './kpi-stat-strip'
import { RevenueChart } from './revenue-chart'
import { GrowthForecastCards } from './growth-forecast-cards'
import { AiInsights } from './ai-insights'
import { HistoricalTrendInsight } from './historical-trend-insight'
import { ReportsTable } from './reports-table'
import { ErrorBanner } from '@/components/error-banner'
import { useMetrics, useChartData, useReports, usePeriods } from '@/lib/hooks/use-dashboard-data'
import { periodContextLabel } from '@/lib/period'
import { selectHeroKpis, selectSecondaryKpis } from '@/lib/kpi-selection'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DollarSign, Users, Wallet, TrendingUp, Percent } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// Background poll interval for the main dashboard's data -- lets the page
// pick up a newly generated report (new KPIs, chart point, AI commentary)
// without the user needing to reload or navigate away and back. Chosen to
// be frequent enough to feel "live" without hammering the backend/Gemini
// for a personal dashboard that isn't updated more than a few times a year.
const DASHBOARD_POLL_INTERVAL_MS = 60_000

// Icon per possible hero-row slot key -- keyed by whichever metric
// selectHeroKpis actually resolved to (e.g. 'ebitda_margin' when 'ebitda'
// itself isn't disclosed by the selected filing), not a fixed 4-key list.
const HERO_ICONS: Record<string, LucideIcon> = {
  revenue: DollarSign,
  ebitda: TrendingUp,
  ebitda_margin: Percent,
  operating_margin: Percent,
  gross_margin: Percent,
  cash: Wallet,
  customers: Users,
}

export function DashboardContainer() {
  // `null` = latest (today's default behavior, no query param sent) --
  // set once the user picks a specific reporting period from the selector
  // below. Not persisted across reloads; a fresh visit always starts on
  // the true latest period.
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null)

  const { data: periods } = usePeriods({ pollIntervalMs: DASHBOARD_POLL_INTERVAL_MS })
  const { data: metrics, loading: metricsLoading, error: metricsError } = useMetrics(selectedDocumentId, {
    pollIntervalMs: DASHBOARD_POLL_INTERVAL_MS,
  })
  // Deliberately not passed `selectedDocumentId` -- the trend chart always
  // shows the whole history regardless of the selected period (see
  // useChartData's own docstring); only the KPI cards/AI insights/ratios
  // anchor on the selection.
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
        <ErrorBanner error={error} />
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

  // The Report row backing whichever period is currently shown -- resolved
  // from metrics.document_id (the backend's own anchor, correct both when a
  // period is explicitly selected and in the default "latest" case) against
  // the reports list already fetched above. `null` when nothing matches yet
  // (e.g. the empty-dashboard state) -- AiInsights still generates live in
  // that case, it just has nothing to persist against.
  const currentReport = (reports ?? []).find((r) => r.document_id === metrics.document_id)

  // Real date context, not a fabricated cadence claim -- every metric below
  // that has an actual prior-period comparative (revenue, ebitda, cash, and
  // the stat-strip ratios) shares the same current period, since they all
  // come from the same single filing. The % change badge shown right next
  // to this text already conveys the comparison, so this is just the
  // current period's own label (e.g. "Jul 2025 - Dec 2025"), not a
  // "prior vs current" comparison string.
  const currentPeriodLabel = (fallback: string) => metrics.current_period || fallback

  // Hero tier -- the metrics a CEO/CFO looks at first, given the large,
  // presentation-slide treatment (see KpiCard's `variant="hero"`). Adaptive,
  // not a fixed 4-key list: selectHeroKpis (lib/kpi-selection.ts) swaps the
  // Profitability slot's own metric (EBITDA -> EBITDA Margin -> Operating
  // Margin -> Gross Margin) when EBITDA itself isn't disclosed by the
  // selected filing, rather than rendering a missing-value sentence in
  // giant hero type -- see docs/dashboard-review.md's adaptive-data section.
  const heroSlots = selectHeroKpis(metrics)

  // Secondary tier: one slot per assignment-required category (Growth &
  // Revenue, Profitability, Cash & Liquidity, Solvency & Leverage, Returns),
  // each with its own fallback chain -- see selectSecondaryKpis. A category
  // with nothing real to show is omitted from the row entirely rather than
  // rendered as an empty card; this is what replaced the old fixed 5-card
  // strip that could (and did, for the FY2025 period) go empty all at once.
  const statStripConfig: StatStripItem[] = selectSecondaryKpis(metrics).map(({ key, category, label, metric }) => ({
    key,
    category,
    label,
    value: metric.value,
    changePercentage: metric.change,
    trend: metric.trend,
    hasComparison: metric.history.length >= 2,
  }))

  // Every figure on this dashboard is EUR-only (Senus is an Irish company;
  // no multi-currency document exists in this project) and every KPI here
  // shares the same "latest" extraction (see get_dashboard_metrics) -- one
  // clear statement at the top of the page, not repeated per card, matches
  // how a real board pack states its "as of" date once on the cover.
  const dataAsOfLabel = metrics.data_extracted_at
    ? new Date(metrics.data_extracted_at).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
      })
    : null

  // Nothing to select with zero or one period -- the dropdown would only
  // ever offer the one period already shown. Periods come back newest
  // first (see GET /metrics/dashboard/periods), so periods[0] is the true
  // latest -- the visual default until the user picks something else.
  const hasPeriodChoice = (periods ?? []).length > 1
  const selectedPeriodValue = String(selectedDocumentId ?? periods?.[0]?.document_id ?? '')

  return (
    <DashboardShell title="Executive Dashboard" description="How the business is performing, at a glance">
      {(dataAsOfLabel || hasPeriodChoice) && (
        <div className="-mt-2 flex flex-wrap items-center justify-between gap-2">
          {dataAsOfLabel ? (
            <p className="text-xs text-muted-foreground">All figures in EUR · Data as of {dataAsOfLabel}</p>
          ) : (
            <span />
          )}
          {hasPeriodChoice && (
            <Select value={selectedPeriodValue} onValueChange={(value) => setSelectedDocumentId(Number(value))}>
              <SelectTrigger aria-label="Select reporting period" className="h-8 w-auto whitespace-nowrap text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {periods!.map((period) => (
                  <SelectItem key={period.document_id} value={String(period.document_id)}>
                    {period.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      )}
      {/* Hero KPI row -- see selectHeroKpis for how the Profitability slot's
          icon/timeframe are resolved consistently with whichever metric it
          actually resolved to. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {heroSlots.map(({ key, title, metric }) => (
          <KpiCard
            key={key}
            variant="hero"
            title={title}
            value={metric.value}
            changePercentage={metric.change}
            trend={metric.trend}
            history={metric.history}
            icon={HERO_ICONS[key] ?? TrendingUp}
            timeframe={
              key === 'customers'
                ? periodContextLabel(metrics.current_period, 'current customer count')
                : currentPeriodLabel('vs prior period')
            }
          />
        ))}
      </div>

      {/* AI Board Insights -- surfaced right under the headline numbers
          (rather than beside the chart, further down) per feedback that the
          narrative commentary should be one of the first things a board
          reader sees, not something they scroll past the chart to find.
          Historical Trend sits alongside it as its own distinct card
          (answers "what's the trajectory over time", not "what does this
          one report say") rather than folded into the same list. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AiInsights metrics={metrics} reportId={currentReport?.id ?? null} />
        </div>
        <HistoricalTrendInsight chartData={chartData ?? []} />
      </div>

      {/* Secondary metrics: Bookings, Profitability, Cash & Liquidity, Solvency & Leverage, Returns */}
      <KpiStatStrip items={statStripConfig} periodLabel={metrics.current_period ?? undefined} />

      {/* Revenue Trend chart -- always the full history, with whichever
          period is selected above highlighted, not filtered to it alone.
          `metrics.document_id` (not the raw `selectedDocumentId` state) --
          the backend already resolves "nothing explicitly selected" to the
          true latest document's own id, so the highlight lands on the
          right point even in the default "latest" state, not nowhere. */}
      <RevenueChart data={chartData ?? []} periodLabel={metrics.current_period} selectedDocumentId={metrics.document_id} />

      {/* Growth & Forecast -- Method Two (guidance-based) projection cards.
          Renders nothing without a real revenue baseline to project from,
          same adaptive discipline as everything else on this page. */}
      <GrowthForecastCards chartData={chartData ?? []} />

      {/* Reports Table */}
      <ReportsTable reports={reports ?? []} onRegenerated={refetchReports} />
    </DashboardShell>
  )
}
