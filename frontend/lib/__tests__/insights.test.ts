import { describe, it, expect } from 'vitest'
import { buildInsightsPrompt, parseInsightsResponse, FALLBACK_INSIGHTS } from '@/lib/insights'

const mockMetrics = {
  revenue: { value: '€836,000', change: 38, trend: 'up' as const },
  customers: { value: '158', change: 2.5, trend: 'up' as const },
  cash: { value: '€1.2M', change: -5, trend: 'down' as const },
  ebitda: { value: '€150K', change: 22, trend: 'up' as const },
}

describe('buildInsightsPrompt', () => {
  it('includes every KPI value and trend', () => {
    const prompt = buildInsightsPrompt(mockMetrics)
    expect(prompt).toContain('€836,000')
    expect(prompt).toContain('trend: up')
    expect(prompt).toContain('trend: down')
  })

  it('asks for the exact JSON shape parseInsightsResponse expects', () => {
    const prompt = buildInsightsPrompt(mockMetrics)
    expect(prompt).toContain('"insights"')
    expect(prompt).toContain('"positive"|"risk"|"opportunity"')
  })
})

describe('parseInsightsResponse', () => {
  it('parses a wrapped {insights: [...]} object', () => {
    const raw = JSON.stringify({ insights: [{ text: 'Revenue is up', type: 'positive' }] })
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Revenue is up', type: 'positive' }])
  })

  it('parses a bare array', () => {
    const raw = JSON.stringify([{ text: 'Cash is tight', type: 'risk' }])
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Cash is tight', type: 'risk' }])
  })

  it('returns null for invalid JSON', () => {
    expect(parseInsightsResponse('not json')).toBeNull()
  })

  it('returns null for an empty array', () => {
    expect(parseInsightsResponse('[]')).toBeNull()
  })

  it('drops entries with an unrecognized type rather than crashing', () => {
    const raw = JSON.stringify({
      insights: [
        { text: 'Valid', type: 'positive' },
        { text: 'Invalid type', type: 'not-a-real-type' },
      ],
    })
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Valid', type: 'positive' }])
  })
})

describe('FALLBACK_INSIGHTS', () => {
  it('is non-empty so the panel never renders blank', () => {
    expect(FALLBACK_INSIGHTS.length).toBeGreaterThan(0)
  })
})
