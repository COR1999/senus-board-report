import { describe, it, expect, beforeEach } from 'vitest'
import { getCachedInsights, setCachedInsights, hasCachedInsightsFor, resetInsightsCache } from '@/lib/insights-cache'
import type { Metrics } from '@/lib/data-service'
import type { Insight } from '@/lib/insights'

const metricsA = { current_period: 'Jul 2025 – Dec 2025' } as unknown as Metrics
const metricsAEquivalent = { current_period: 'Jul 2025 – Dec 2025' } as unknown as Metrics
const metricsB = { current_period: 'Jul 2024 – Dec 2024' } as unknown as Metrics
const insights: Insight[] = [{ text: 'ANY_TEXT', type: 'positive', action: 'ANY_ACTION' }]

describe('insights-cache', () => {
  beforeEach(() => {
    resetInsightsCache()
  })

  it('returns null when nothing has been cached yet', () => {
    expect(getCachedInsights(metricsA)).toBeNull()
    expect(hasCachedInsightsFor(metricsA)).toBe(false)
  })

  it('returns the cached insights for content-equal metrics, even a different object reference', () => {
    setCachedInsights(metricsA, insights)
    expect(getCachedInsights(metricsAEquivalent)).toEqual(insights)
    expect(hasCachedInsightsFor(metricsAEquivalent)).toBe(true)
  })

  it('misses the cache once the metrics content actually changes', () => {
    setCachedInsights(metricsA, insights)
    expect(getCachedInsights(metricsB)).toBeNull()
    expect(hasCachedInsightsFor(metricsB)).toBe(false)
  })
})
