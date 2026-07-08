'use client'

import { useEffect, useState } from 'react'
import { Sparkles, TrendingUp, TriangleAlert, Lightbulb, RefreshCw, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getAiInsights, getStoredInsights, saveInsights, type Metrics } from '@/lib/data-service'
import { FALLBACK_INSIGHTS, type Insight, type InsightType } from '@/lib/insights'
import { cn } from '@/lib/utils'

interface AiInsightsProps {
  metrics: Metrics
  /** The `Report.id` backing the currently-selected period, resolved by
   * `dashboard-container.tsx` from `metrics.document_id` against the
   * already-fetched reports list. `null` when no matching report exists yet
   * (e.g. the empty-dashboard state) -- insights still generate live in
   * that case, they just have nothing to persist against. */
  reportId: number | null
}

// Fixed status roles, not a categorical series -- each insight is one of
// these three states, always paired with an icon + label, never color alone.
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
}

export function AiInsights({ metrics, reportId }: AiInsightsProps) {
  const [insights, setInsights] = useState<Insight[]>(FALLBACK_INSIGHTS)
  const [loading, setLoading] = useState(true)
  // Whether a persisted row exists on the backend for `reportId` right now
  // (just loaded, or just saved after a live generation) -- this, not a
  // metrics content-hash, is what gates the manual refresh button. Tied to
  // *this specific extraction* via report_id rather than "these particular
  // numbers happened to repeat," a stronger key than the old localStorage
  // cache used.
  const [hasStored, setHasStored] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    async function load() {
      if (reportId != null) {
        const stored = await getStoredInsights(reportId).catch(() => null)
        if (cancelled) return
        if (stored) {
          setInsights(stored.insights)
          setHasStored(true)
          setLoading(false)
          return
        }
      }

      // No report to check, or nothing stored for it yet -- generate live
      // and persist the result so this report never re-spends Gemini quota
      // once a real generation succeeds.
      const { insights: result, isFallback, model } = await getAiInsights(metrics)
      if (cancelled) return
      setInsights(result)
      setLoading(false)
      if (!isFallback && reportId != null) {
        setHasStored(true)
        saveInsights(reportId, result, model).catch(() => {
          // Persistence is a durability optimization, not a correctness
          // requirement -- the panel already shows the real result either way.
        })
      } else {
        setHasStored(false)
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [reportId, metrics])

  const handleRefresh = () => {
    if (loading || hasStored) return

    setLoading(true)
    getAiInsights(metrics).then(({ insights: result, isFallback, model }) => {
      setInsights(result)
      setLoading(false)
      if (!isFallback && reportId != null) {
        setHasStored(true)
        saveInsights(reportId, result, model).catch(() => {})
      }
    })
  }

  const refreshDisabled = loading || hasStored

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
            onClick={handleRefresh}
            disabled={refreshDisabled}
            title={
              !loading && hasStored
                ? 'Already up to date -- upload a new report to regenerate'
                : 'Regenerate insights from the current data'
            }
          >
            <RefreshCw className={cn('h-5 w-5', loading && 'animate-spin')} />
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
            {insights.map((insight, index) => {
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
                    {/* Same caption treatment as KpiStatStrip's category
                        label, so an insight visually anchors to the same
                        section of the dashboard it's commenting on. */}
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
