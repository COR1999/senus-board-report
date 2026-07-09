'use client'

import { useEffect, useState } from 'react'
import {
  getHistoricalTrendInsight,
  getStoredHistoricalInsight,
  saveHistoricalInsight,
  type ChartDataPoint,
} from '@/lib/data-service'
import type { Insight } from '@/lib/insights'

export interface UseHistoricalTrendInsightResult {
  insight: Insight | null
  loading: boolean
  /** A trend needs at least 2 real points to describe -- with 0 or 1,
   * there's nothing to say yet that isn't a single number restated. */
  hasEnoughHistory: boolean
}

/**
 * The single AI-generated insight describing the trend across every report
 * on file (not one report's own snapshot -- see useAiInsights for that).
 * Persisted server-side, keyed by a fingerprint of the current chart data
 * rather than a report id -- there's exactly one "trend across all
 * reports" for this whole single-user dashboard. Extracted out of the old
 * historical-trend-insight.tsx (now folded into AiInsights' own ranked
 * feed, see docs/dashboard-review.md) for the same reuse reason as
 * useAiInsights.
 */
export function useHistoricalTrendInsight(chartData: ChartDataPoint[]): UseHistoricalTrendInsightResult {
  const hasEnoughHistory = chartData.length >= 2

  const [insight, setInsight] = useState<Insight | null>(null)
  // Initialized from hasEnoughHistory (computed above, at hook-call time,
  // not inside the effect) rather than reset via a synchronous setState
  // call in the effect body -- avoids react-hooks/set-state-in-effect
  // while still starting "loading" only when a fetch is actually about to
  // happen. Doesn't re-flip to true if hasEnoughHistory later goes from
  // true back to false (chartData shrinking below 2 points) -- not a real
  // scenario in practice, since chart history only ever grows as new
  // reports are ingested.
  const [loading, setLoading] = useState(hasEnoughHistory)

  useEffect(() => {
    if (!hasEnoughHistory) return

    let cancelled = false

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
          // Persistence is a durability optimization -- the panel already
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

  return { insight, loading, hasEnoughHistory }
}
