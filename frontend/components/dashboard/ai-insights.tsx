'use client'

import { Sparkles, TrendingUp, TriangleAlert, Lightbulb, RefreshCw, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAiInsights } from '@/lib/hooks/use-ai-insights'
import { useHistoricalTrendInsight } from '@/lib/hooks/use-historical-trend-insight'
import type { Metrics, ChartDataPoint } from '@/lib/data-service'
import { type Insight, type InsightType } from '@/lib/insights'
import { cn } from '@/lib/utils'

interface AiInsightsProps {
  metrics: Metrics
  /** The `Report.id` backing the currently-selected period, resolved by
   * `dashboard-container.tsx` from `metrics.document_id` against the
   * already-fetched reports list. `null` when no matching report exists yet
   * (e.g. the empty-dashboard state) -- insights still generate live in
   * that case, they just have nothing to persist against. */
  reportId: number | null
  /** Same all-reports chart data the Revenue Trend chart renders -- powers
   * the trailing "Trend" entry describing the trajectory across every
   * report on file. Folded into this same ranked list (not a separate
   * adjacent card, see the old historical-trend-insight.tsx) since the two
   * answer related questions and a board reader shouldn't have to look in
   * two places for "what does the data say." */
  chartData: ChartDataPoint[]
}

// Fixed status roles, not a categorical series -- each insight is one of
// these states, always paired with an icon + label, never color alone.
const INSIGHT_STYLE: Record<InsightType, { badgeClass: string; Icon: typeof TrendingUp; label: string }> = {
  positive: {
    badgeClass: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
    Icon: TrendingUp,
    label: 'Positive',
  },
  risk: {
    badgeClass: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    Icon: TriangleAlert,
    label: 'Risk',
  },
  opportunity: {
    badgeClass: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    Icon: Lightbulb,
    label: 'Opportunity',
  },
  trend: {
    badgeClass: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    Icon: TrendingUp,
    label: 'Trend',
  },
}

/**
 * The dashboard's closing "AI Executive Commentary" section -- a single
 * ranked feed merging this report's own insights (useAiInsights) with the
 * all-reports trend narrative (useHistoricalTrendInsight), rather than two
 * competing cards. Positioned at the bottom of the page (see
 * dashboard-container.tsx) so it reads as a synthesis of everything above
 * it, not a preview shown before the reader has seen the numbers.
 */
export function AiInsights({ metrics, reportId, chartData }: AiInsightsProps) {
  const { insights, loading: insightsLoading, hasStored, refresh } = useAiInsights(metrics, reportId)
  const { insight: trendInsight, loading: trendLoading, hasEnoughHistory } = useHistoricalTrendInsight(chartData)

  const loading = insightsLoading || (hasEnoughHistory && trendLoading)
  const combined: Insight[] = trendInsight ? [...insights, trendInsight] : insights
  const refreshDisabled = insightsLoading || hasStored

  return (
    <Card className="border-foreground/10">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-blue-600" />
          <CardTitle>AI Board Insights</CardTitle>
        </div>
        <CardAction>
          <Button
            variant="ghost"
            size="icon"
            onClick={refresh}
            disabled={refreshDisabled}
            title={
              !insightsLoading && hasStored
                ? 'Already up to date -- upload a new report to regenerate'
                : 'Regenerate insights from the current data'
            }
          >
            <RefreshCw className={cn('h-5 w-5', insightsLoading && 'animate-spin')} />
            <span className="sr-only">Refresh AI insights</span>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="animate-pulse space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-4 bg-muted rounded w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {combined.map((insight, index) => {
              const { badgeClass, Icon, label } = INSIGHT_STYLE[insight.type]
              return (
                <div key={index} className="flex gap-3">
                  {/* Fixed width (not the Badge default w-fit) so every row's
                      badge is the same width regardless of label length
                      ("Positive" vs "Opportunity") -- otherwise the text
                      column below starts at a different x on every row,
                      which reads as broken left-alignment. */}
                  <Badge className={`mt-1 h-fit w-28 flex-shrink-0 gap-1 ${badgeClass}`}>
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </Badge>
                  <div className="min-w-0 flex-1 space-y-1">
                    {insight.category && (
                      <span className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {insight.category}
                      </span>
                    )}
                    <p className="text-sm leading-relaxed text-foreground/90">{insight.text}</p>
                    {insight.action && (
                      <p className="flex items-start gap-1 text-xs text-muted-foreground">
                        <ArrowRight className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                        {insight.action}
                      </p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
