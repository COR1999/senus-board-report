import { describe, it, expect } from 'vitest'
import { buildInsightsPrompt, parseInsightsResponse, FALLBACK_INSIGHTS } from '@/lib/insights'

const mockMetrics = {
  revenue: { value: '€836,000', change: 38, trend: 'up' as const, history: [] },
  customers: { value: '158', change: 2.5, trend: 'up' as const, history: [] },
  cash: { value: '€1.2M', change: -5, trend: 'down' as const, history: [] },
  ebitda: { value: '€150K', change: 22, trend: 'up' as const, history: [] },
  ebitda_margin: { value: '18.2%', change: 3.1, trend: 'up' as const, history: [] },
  cash_runway: { value: '14.5 mo', change: 20.8, trend: 'up' as const, history: [] },
  interest_cover: { value: '8.4x', change: 12, trend: 'up' as const, history: [] },
  roce: { value: '24.1%', change: 5.4, trend: 'up' as const, history: [] },
  bookings: { value: '€700K', change: 0, trend: 'neutral' as const, history: [] },
  current_period: 'H1 2025',
  prior_period: 'H1 2024',
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

  it('asks for exactly 3 insights, each with a distinct recommended action', () => {
    const prompt = buildInsightsPrompt(mockMetrics)
    expect(prompt).toContain('exactly 3')
    expect(prompt).toContain('"action"')
  })

  it('lists the 5 assignment KPI categories and mentions the Revenue Trend chart', () => {
    const prompt = buildInsightsPrompt(mockMetrics)
    expect(prompt).toContain('Growth & Revenue')
    expect(prompt).toContain('Profitability')
    expect(prompt).toContain('Cash & Liquidity')
    expect(prompt).toContain('Solvency & Leverage')
    expect(prompt).toContain('Returns')
    expect(prompt).toContain('Revenue Trend chart')
  })
})

describe('parseInsightsResponse', () => {
  it('parses a wrapped {insights: [...]} object', () => {
    const raw = JSON.stringify({ insights: [{ text: 'Revenue is up', type: 'positive' }] })
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Revenue is up', type: 'positive', action: '', category: undefined }])
  })

  it('parses a bare array', () => {
    const raw = JSON.stringify([{ text: 'Cash is tight', type: 'risk' }])
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Cash is tight', type: 'risk', action: '', category: undefined }])
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
    expect(parseInsightsResponse(raw)).toEqual([{ text: 'Valid', type: 'positive', action: '', category: undefined }])
  })

  it('parses a well-formed response including action and category', () => {
    const raw = JSON.stringify({
      insights: [
        { text: 'Revenue grew 38%.', type: 'positive', action: 'Keep investing in UK sales.', category: 'Growth & Revenue' },
      ],
    })

    expect(parseInsightsResponse(raw)).toEqual([
      { text: 'Revenue grew 38%.', type: 'positive', action: 'Keep investing in UK sales.', category: 'Growth & Revenue' },
    ])
  })

  it('drops an unrecognized category rather than rejecting the insight', () => {
    const raw = JSON.stringify({
      insights: [
        { text: 'Headcount grew.', type: 'positive', action: 'Keep hiring.', category: 'Not A Real Category' },
      ],
    })

    const result = parseInsightsResponse(raw)
    expect(result).toHaveLength(1)
    expect(result?.[0].category).toBeUndefined()
  })
})

describe('FALLBACK_INSIGHTS', () => {
  it('is non-empty so the panel never renders blank', () => {
    expect(FALLBACK_INSIGHTS.length).toBeGreaterThan(0)
  })
})
