'use client'

import { useEffect, useState } from 'react'
import { getAiInsights, getStoredInsights, saveInsights, type Metrics } from '@/lib/data-service'
import { FALLBACK_INSIGHTS, type Insight } from '@/lib/insights'

export interface UseAiInsightsResult {
  insights: Insight[]
  loading: boolean
  /** Whether a persisted row exists on the backend for `reportId` right now
   * -- gates the manual refresh control. Tied to *this specific extraction*
   * via report_id rather than a metrics content-hash, a stronger key than
   * "these particular numbers happened to repeat." */
  hasStored: boolean
  /** Re-generates live from Gemini -- a no-op while already loading or
   * while a stored, up-to-date result exists for this report (nothing new
   * to regenerate). */
  refresh: () => void
}

/**
 * Per-report AI Board Insights: checks the backend's persisted result first
 * (see backend/app/models/report_insights.py), falls back to a live Gemini
 * generation via /api/insights, and persists a real (non-fallback) result
 * so a report never re-spends Gemini quota once a real generation
 * succeeds. Extracted out of ai-insights.tsx so the data-fetching concern
 * is independently reusable -- AiInsights composes this alongside
 * useHistoricalTrendInsight to render one merged, ranked feed instead of
 * two separate cards (see docs/dashboard-review.md's "AI commentary"
 * section).
 */
export function useAiInsights(metrics: Metrics, reportId: number | null): UseAiInsightsResult {
  const [insights, setInsights] = useState<Insight[]>(FALLBACK_INSIGHTS)
  const [loading, setLoading] = useState(true)
  const [hasStored, setHasStored] = useState(false)

  useEffect(() => {
    let cancelled = false

    // Deliberately no synchronous setLoading(true) reset here (would trip
    // react-hooks/set-state-in-effect, calling setState synchronously in an
    // effect body rather than in response to an external event) -- the
    // initial mount is already `loading: true` via useState's own initial
    // value, and a later reportId/metrics change (e.g. selecting a
    // different period) intentionally keeps showing the previous content
    // until the new fetch resolves rather than flashing back to a
    // skeleton, matching lib/hooks/use-async-data.ts's own identical
    // choice for the exact same reason.
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

  const refresh = () => {
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

  return { insights, loading, hasStored, refresh }
}
