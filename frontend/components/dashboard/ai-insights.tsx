'use client'

import { useEffect, useState } from 'react'
import { Sparkles, TrendingUp, TriangleAlert, Lightbulb } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getAiInsights, type Metrics } from '@/lib/data-service'
import { FALLBACK_INSIGHTS, type Insight, type InsightType } from '@/lib/insights'

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
  const [insights, setInsights] = useState<Insight[]>(FALLBACK_INSIGHTS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    getAiInsights(metrics).then((result) => {
      if (!cancelled) {
        setInsights(result)
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [metrics])

  return (
    <Card className="col-span-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-blue-600" />
          <div>
            <CardTitle>AI Board Insights</CardTitle>
            <CardDescription>AI-generated executive commentary</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="animate-pulse space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-4 bg-muted rounded w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {insights.map((insight, index) => {
              const { badgeClass, Icon, label } = INSIGHT_STYLE[insight.type]
              return (
                <div key={index} className="flex gap-3">
                  <Badge className={`mt-1 h-fit flex-shrink-0 gap-1 ${badgeClass}`}>
                    <Icon className="h-3 w-3" />
                    {label}
                  </Badge>
                  <p className="text-sm text-foreground leading-relaxed">{insight.text}</p>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
