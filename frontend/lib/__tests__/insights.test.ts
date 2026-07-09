import { describe, it, expect } from 'vitest'
import {
  buildInsightsPrompt,
  buildHistoricalInsightPrompt,
  parseInsightsResponse,
  FALLBACK_INSIGHTS,
  FALLBACK_TREND_INSIGHT,
} from '@/lib/insights'
import type { ChartDataPoint } from '@/lib/data-service'

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
  current_period: 'Jul 2025 – Dec 2025',
  prior_period: 'Jul 2024 – Dec 2024',
  data_extracted_at: '2026-03-19T08:38:00',
  document_id: 1,
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

  it('excludes the plain string/null context fields, not just the real KPI cards', () => {
    // Real bug, live-confirmed against production: `Metrics` mixes
    // MetricValue-shaped KPI cards with plain string|null context fields
    // (current_period/prior_period/data_extracted_at). Blindly iterating
    // every key previously produced "- current_period: undefined
    // (undefined%, trend: undefined)" garbage lines, and a null
    // prior_period threw outright (reading .value off null) -- caught by
    // the API route's try/catch, silently falling back to the hardcoded
    // FALLBACK_INSIGHTS text even for genuinely new, real KPI data.
    const prompt = buildInsightsPrompt(mockMetrics)
    expect(prompt).not.toContain('current_period')
    expect(prompt).not.toContain('prior_period')
    expect(prompt).not.toContain('data_extracted_at')
    expect(prompt).not.toContain('undefined')
  })

  it('does not throw when prior_period/data_extracted_at are null', () => {
    const metricsWithNulls = { ...mockMetrics, prior_period: null, data_extracted_at: null }
    expect(() => buildInsightsPrompt(metricsWithNulls)).not.toThrow()
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

  it('accepts a "trend" type (used by the historical-insight prompt), not just positive/risk/opportunity', () => {
    const raw = JSON.stringify({ insights: [{ text: 'Revenue has grown steadily', type: 'trend', action: 'Keep it up' }] })
    expect(parseInsightsResponse(raw)).toEqual([
      { text: 'Revenue has grown steadily', type: 'trend', action: 'Keep it up', category: undefined },
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

describe('buildHistoricalInsightPrompt', () => {
  const mixedCadenceData: ChartDataPoint[] = [
    { period: 'FY2024', revenue: 700_000, ebitda: -50_000, cash: 400_000, document_id: 1, cadence_months: 12 },
    { period: 'HY2025', revenue: 350_000, ebitda: -20_000, cash: 500_000, document_id: 2, cadence_months: 6 },
    { period: 'FY2025', revenue: 836_991, ebitda: -613_313, cash: 140_135, document_id: 3, cadence_months: 12 },
  ]

  it('describes Full-Year and Half-Year periods in separate lists, not one blended sequence', () => {
    const prompt = buildHistoricalInsightPrompt(mixedCadenceData)

    expect(prompt).toContain('Full-Year periods, oldest to newest: FY2024')
    expect(prompt).toContain('Half-Year periods, oldest to newest: HY2025')
  })

  it('warns against blending the two cadences into one implied sequence', () => {
    const prompt = buildHistoricalInsightPrompt(mixedCadenceData)
    expect(prompt).toContain('NOT directly comparable magnitudes')
  })

  it('asks for exactly 1 insight of type "trend"', () => {
    const prompt = buildHistoricalInsightPrompt(mixedCadenceData)
    expect(prompt).toContain('exactly 1')
    expect(prompt).toContain('"trend"')
  })

  it('reports "none reported yet" for a cadence with zero points, rather than an empty list', () => {
    const onlyFullYear: ChartDataPoint[] = [
      { period: 'FY2025', revenue: 836_991, ebitda: -613_313, cash: 140_135, document_id: 1, cadence_months: 12 },
    ]
    const prompt = buildHistoricalInsightPrompt(onlyFullYear)
    expect(prompt).toContain('Half-Year periods, oldest to newest: none reported yet')
  })

  it('routes an undeterminable cadence into neither Full-Year nor Half-Year', () => {
    const unknownCadence: ChartDataPoint[] = [
      { period: 'FY2025', revenue: 836_991, ebitda: -613_313, cash: 140_135, document_id: 1, cadence_months: 12 },
      { period: 'Unknown', revenue: 100, ebitda: null, cash: null, document_id: 2, cadence_months: null },
    ]
    const prompt = buildHistoricalInsightPrompt(unknownCadence)
    expect(prompt).not.toContain('Unknown:')
  })
})

describe('FALLBACK_TREND_INSIGHT', () => {
  it('is typed "trend", distinct from the 3-item report-scoped fallback', () => {
    expect(FALLBACK_TREND_INSIGHT.type).toBe('trend')
  })
})
