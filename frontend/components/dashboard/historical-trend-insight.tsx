'use client'

import { useEffect, useState } from 'react'
import { TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  getHistoricalTrendInsight,
  getStoredHistoricalInsight,
  saveHistoricalInsight,
  type ChartDataPoint,
} from '@/lib/data-service'
import type { Insight } from '@/lib/insights'

interface HistoricalTrendInsightProps {
  /** Same all-reports chart data the Revenue Trend chart renders -- this
   * card describes the trajectory across ALL of it, not one report's own
   * snapshot (see AiInsights for that). */
  chartData: ChartDataPoint[]
}

/**
 * A single AI-generated insight describing the trend across every report on
 * file, shown as its own clearly-labeled card next to AI Board Insights
 * rather than folded into that panel -- the two answer different questions
 * ("what does this one report say" vs. "what's the trajectory over time")
 * and mixing them into one list would blur that distinction.
 *
 * Persisted server-side (see backend/app/models/historical_insight.py),
 * keyed by a fingerprint of the current chart data rather than a report id
 * -- there's exactly one "trend across all reports" for this whole
 * single-user dashboard, unlike per-report insights.
 */
export function HistoricalTrendInsight({ chartData }: HistoricalTrendInsightProps) {
  const [insight, setInsight] = useState<Insight | null>(null)
  const [loading, setLoading] = useState(true)

  // A trend needs at least 2 real points to describe -- with 0 or 1, there's
  // nothing to say yet that isn't a single number restated. Real points
  // only (a chart's own synthetic prior-period point has document_id=null
  // but still carries real embedded prior-period data, so it still counts).
  const hasEnoughHistory = chartData.length >= 2

  useEffect(() => {
    if (!hasEnoughHistory) {
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)

    async function load() {
      const stored = await getStoredHistoricalInsight().catch(() => null)
      if (cancelled) return
      if (stored) {
        setInsight(stored.insight)
        setLoading(false)
        return
      }

      const { insights: result, isFallback, model } = await getHistoricalTrendInsight(chartData)
      if (cancelled) return
      const generated = result[0] ?? null
      setInsight(generated)
      setLoading(false)
      if (generated && !isFallback) {
        saveHistoricalInsight(generated, model).catch(() => {
          // Persistence is a durability optimization -- the card already
          // shows the real result either way.
        })
      }
    }

    load()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed on chartData's own length/content below, not object identity, since a poll can return a structurally-identical-but-new array.
  }, [hasEnoughHistory, JSON.stringify(chartData)])

  if (!hasEnoughHistory) return null

  return (
    <Card className="border-foreground/10">
      <CardHeader>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-blue-600" />
          <CardTitle>Historical Trend</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-4 bg-muted rounded w-full" />
            <div className="h-4 bg-muted rounded w-2/3" />
          </div>
        ) : insight ? (
          <div className="space-y-2">
            <Badge className="h-fit gap-1 bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
              <TrendingUp className="h-3.5 w-3.5" />
              Trend
            </Badge>
            <p className="text-sm leading-relaxed text-foreground/90">{insight.text}</p>
            {insight.action && (
              <p className="text-xs text-muted-foreground">{insight.action}</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Trend commentary unavailable right now.</p>
        )}
      </CardContent>
    </Card>
  )
}
