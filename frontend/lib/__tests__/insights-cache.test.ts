import { describe, it, expect, beforeEach, afterEach } from 'vitest'
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

describe('insights-cache localStorage persistence', () => {
  afterEach(() => {
    resetInsightsCache()
  })

  it('survives a simulated page reload (module re-evaluated from a fresh localStorage read)', async () => {
    setCachedInsights(metricsA, insights)

    // Simulates a hard browser refresh -- the module's own in-memory state
    // is gone, but localStorage isn't; re-importing it fresh (vitest's
    // module registry reset) should rehydrate from what was persisted.
    const { vi } = await import('vitest')
    vi.resetModules()
    const reloaded = await import('@/lib/insights-cache')

    expect(reloaded.getCachedInsights(metricsAEquivalent)).toEqual(insights)
  })

  it('resetInsightsCache clears the persisted entry too, not just in-memory state', async () => {
    setCachedInsights(metricsA, insights)
    resetInsightsCache()

    const { vi } = await import('vitest')
    vi.resetModules()
    const reloaded = await import('@/lib/insights-cache')

    expect(reloaded.getCachedInsights(metricsAEquivalent)).toBeNull()
  })
})
