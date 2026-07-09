import { describe, it, expect } from 'vitest'
import {
  selectHeroKpis,
  selectSecondaryKpis,
  revenuePerCustomerMetric,
  netCashMovementMetric,
  revenueGrowthMetric,
} from '@/lib/kpi-selection'
import type { Metrics, MetricValue } from '@/lib/data-service'

const available = (over: Partial<MetricValue> = {}): MetricValue => ({
  value: 'ANY', change: 0, trend: 'neutral', history: [], available: true, ...over,
})
const missing = (value = 'Not reported'): MetricValue => ({
  value, change: 0, trend: 'neutral', history: [], available: false,
})

function baseMetrics(overrides: Partial<Metrics> = {}): Metrics {
  return {
    revenue: available({ value: '€837K', change: 21.6, trend: 'up', history: [688317, 837000] }),
    customers: available({ value: '36', history: [30, 36] }),
    cash: available({ value: '€140K', history: [200000, 140000] }),
    ebitda: available({ value: '€150K' }),
    ebitda_margin: available({ value: '18.2%' }),
    cash_runway: available({ value: '14.5 mo' }),
    interest_cover: available({ value: '8.4x' }),
    roce: available({ value: '24.1%' }),
    bookings: available({ value: '€700K' }),
    gross_margin: available({ value: '61.4%' }),
    operating_margin: available({ value: '18.2%' }),
    current_period: 'FY2025',
    prior_period: 'FY2024',
    data_extracted_at: '2026-07-08T00:00:00Z',
    document_id: 1,
    ...overrides,
  }
}

describe('selectHeroKpis', () => {
  it('uses EBITDA directly when it is available', () => {
    const slots = selectHeroKpis(baseMetrics())
    expect(slots.map((s) => s.key)).toEqual(['revenue', 'ebitda', 'cash', 'customers'])
  })

  it('falls back to EBITDA Margin when EBITDA is not disclosed', () => {
    const slots = selectHeroKpis(baseMetrics({ ebitda: missing('EBITDA not reported in this filing') }))
    expect(slots.map((s) => s.key)).toEqual(['revenue', 'ebitda_margin', 'cash', 'customers'])
    expect(slots.find((s) => s.key === 'ebitda_margin')?.title).toBe('EBITDA Margin')
  })

  it('falls through the whole profitability chain to Gross Margin', () => {
    const slots = selectHeroKpis(
      baseMetrics({
        ebitda: missing(),
        ebitda_margin: missing(),
        operating_margin: missing(),
      })
    )
    expect(slots.map((s) => s.key)).toEqual(['revenue', 'gross_margin', 'cash', 'customers'])
  })

  it('omits the profitability slot entirely rather than rendering a missing card', () => {
    const slots = selectHeroKpis(
      baseMetrics({ ebitda: missing(), ebitda_margin: missing(), operating_margin: missing(), gross_margin: missing() })
    )
    expect(slots.map((s) => s.key)).toEqual(['revenue', 'cash', 'customers'])
  })
})

describe('selectSecondaryKpis', () => {
  it('resolves every category to its primary metric when all are available', () => {
    const slots = selectSecondaryKpis(baseMetrics())
    expect(slots.map((s) => s.key)).toEqual(['bookings', 'ebitda_margin', 'cash_runway', 'interest_cover', 'roce'])
  })

  it('omits a category entirely when its whole fallback chain is unavailable (the FY2025 case)', () => {
    // Mirrors the real FY2025 Information Document: only revenue/cash/
    // customers are disclosed, nothing balance-sheet-derived.
    const slots = selectSecondaryKpis(
      baseMetrics({
        bookings: missing(),
        ebitda_margin: missing(),
        cash_runway: missing(),
        interest_cover: missing(),
        roce: missing(),
        operating_margin: missing(),
        gross_margin: missing(),
      })
    )
    // Growth & Revenue falls back to Revenue Growth (real, 2+ history points);
    // Cash & Liquidity falls back to Net Cash Movement (derived from cash's own
    // history, doesn't need a balance-sheet row at all); Returns falls back to
    // Revenue per Customer. Profitability and Solvency & Leverage have nothing
    // left in their chains and are correctly omitted.
    expect(slots.map((s) => s.key)).toEqual(['revenue_growth', 'net_cash_movement', 'revenue_per_customer'])
  })

  it('never shows the same metric twice across two categories (dedup)', () => {
    // Solvency & Leverage's own chain (Interest Cover -> EBITDA Margin ->
    // Operating Margin) must skip EBITDA Margin here since Profitability
    // already claimed it, landing on Operating Margin instead -- not a
    // second, duplicate "EBITDA Margin" card.
    const slots = selectSecondaryKpis(baseMetrics({ interest_cover: missing() }))
    const ebitdaMarginSlots = slots.filter((s) => s.key === 'ebitda_margin')
    expect(ebitdaMarginSlots).toHaveLength(1)
    expect(slots.map((s) => s.key)).toEqual([
      'bookings', 'ebitda_margin', 'cash_runway', 'operating_margin', 'roce',
    ])
  })

  it('falls back Cash & Liquidity to Net Cash Movement when Cash Runway is unavailable', () => {
    const slots = selectSecondaryKpis(baseMetrics({ cash_runway: missing() }))
    const cash = slots.find((s) => s.key === 'net_cash_movement')
    expect(cash).toBeDefined()
    expect(cash?.category).toBe('Cash & Liquidity')
  })
})

describe('revenuePerCustomerMetric', () => {
  it('divides the latest real revenue by the latest real customer count', () => {
    const metric = revenuePerCustomerMetric(baseMetrics())
    expect(metric).not.toBeNull()
    expect(metric?.value).toBe('€23K') // 837000 / 36 ≈ 23250
  })

  it('returns null when customers is unavailable', () => {
    expect(revenuePerCustomerMetric(baseMetrics({ customers: missing() }))).toBeNull()
  })
})

describe('netCashMovementMetric', () => {
  it('is the delta between the two most recent real cash points', () => {
    const metric = netCashMovementMetric(baseMetrics())
    expect(metric?.trend).toBe('down')
    expect(metric?.value).toBe('-€60K') // 140000 - 200000
  })

  it('returns null with fewer than two real history points', () => {
    expect(netCashMovementMetric(baseMetrics({ cash: available({ history: [140000] }) }))).toBeNull()
  })
})

describe('revenueGrowthMetric', () => {
  it('mirrors revenue change/trend when a real prior comparative exists', () => {
    const metric = revenueGrowthMetric(baseMetrics())
    expect(metric?.value).toBe('+21.6%')
    expect(metric?.trend).toBe('up')
  })

  it('returns null without a real prior-period comparative', () => {
    expect(
      revenueGrowthMetric(baseMetrics({ revenue: available({ history: [837000], change: 0 }) }))
    ).toBeNull()
  })
})
