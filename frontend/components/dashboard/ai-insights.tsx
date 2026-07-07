'use client'

import { useEffect, useState } from 'react'
import { Sparkles, TrendingUp, TriangleAlert, Lightbulb, RefreshCw, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { getAiInsights, type Metrics } from '@/lib/data-service'
import { FALLBACK_INSIGHTS, type Insight, type InsightType } from '@/lib/insights'
import { getCachedInsights, setCachedInsights, hasCachedInsightsFor } from '@/lib/insights-cache'
import { cn } from '@/lib/utils'

interface AiInsightsProps {
  metrics: Metrics
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

export function AiInsights({ metrics }: AiInsightsProps) {
  // Keyed by metrics *content*, not object reference, and stored at module
  // scope (see lib/insights-cache.ts) -- what actually matters is whether a
  // new report has landed since the last call, not how long ago the button
  // was clicked or whether this component instance happens to still be
  // mounted. A per-instance ref/state guard here would reset every time a
  // user navigates away (e.g. to Settings to change the theme) and back,
  // triggering a wasted, non-deterministic Gemini re-call on unchanged data.
  const cached = getCachedInsights(metrics)
  const [insights, setInsights] = useState<Insight[]>(cached ?? FALLBACK_INSIGHTS)
  const [loading, setLoading] = useState(cached === null)

  useEffect(() => {
    const alreadyCached = getCachedInsights(metrics)
    if (alreadyCached) {
      setInsights(alreadyCached)
      setLoading(false)
      return
    }

    let cancelled = false

    setLoading(true)
    getAiInsights(metrics).then((result) => {
      if (!cancelled) {
        setInsights(result)
        setLoading(false)
        setCachedInsights(metrics, result)
      }
    })

    return () => {
      cancelled = true
    }
  }, [metrics])

  const hasNewData = !hasCachedInsightsFor(metrics)

  const handleRefresh = () => {
    if (loading || !hasNewData) return

    setLoading(true)
    getAiInsights(metrics).then((result) => {
      setInsights(result)
      setLoading(false)
      setCachedInsights(metrics, result)
    })
  }

  const refreshDisabled = loading || !hasNewData

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
              !loading && !hasNewData
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
