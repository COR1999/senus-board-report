import { render, screen } from '@testing-library/react'
import { CostWaterfallChart, buildWaterfallRows } from '@/components/dashboard/cost-waterfall-chart'
import { describe, it, expect } from 'vitest'
import type { CostWaterfall } from '@/lib/data-service'

function waterfall(overrides: Partial<CostWaterfall> = {}): CostWaterfall {
  return {
    available: true,
    revenue: 837_000,
    cost_of_sales: 300_000,
    gross_profit: 537_000,
    administrative_expenses: 450_000,
    operating_result: 87_000,
    depreciation_amortization: 63_000,
    ebitda: 150_000,
    document_id: 1,
    ...overrides,
  }
}

describe('buildWaterfallRows', () => {
  it('builds a (start, end) span per step from a fully-disclosed period', () => {
    const rows = buildWaterfallRows(waterfall())

    expect(rows.map((r) => r.label)).toEqual([
      'Revenue', 'Cost of Sales', 'Gross Profit', 'Operating Costs', 'Operating Result', 'D&A', 'EBITDA',
    ])
    expect(rows.find((r) => r.label === 'Revenue')).toMatchObject({ base: 0, display: 837_000, end: 837_000, type: 'total' })
    expect(rows.find((r) => r.label === 'Cost of Sales')).toMatchObject({ base: 537_000, display: 300_000, type: 'decrease' })
    expect(rows.find((r) => r.label === 'EBITDA')).toMatchObject({ base: 0, display: 150_000, end: 150_000, type: 'total' })
  })

  it('draws a negative subtotal below the axis instead of assuming positive figures', () => {
    // A loss-making operating result -- real for a company like Senus.
    const rows = buildWaterfallRows(waterfall({ operating_result: -50_000, ebitda: 13_000, depreciation_amortization: 63_000 }))

    const operatingResult = rows.find((r) => r.label === 'Operating Result')
    expect(operatingResult).toMatchObject({ base: -50_000, display: 50_000, end: -50_000, type: 'total' })

    // D&A still adds back correctly from a negative starting point.
    const da = rows.find((r) => r.label === 'D&A')
    expect(da).toMatchObject({ base: -50_000, display: 63_000, end: 13_000, type: 'increase' })
  })

  it('returns nothing when the period is not marked available', () => {
    expect(buildWaterfallRows(waterfall({ available: false }))).toEqual([])
  })

  it('returns nothing when any required figure is missing, even if available is true', () => {
    expect(buildWaterfallRows(waterfall({ operating_result: null }))).toEqual([])
    expect(buildWaterfallRows(waterfall({ ebitda: null }))).toEqual([])
  })
})

describe('CostWaterfallChart', () => {
  it('renders the chart chrome for a fully-disclosed period', () => {
    render(<CostWaterfallChart data={waterfall()} periodLabel="Jul 2025 - Dec 2025" />)

    expect(screen.getByText('Cost Waterfall')).toBeInTheDocument()
    expect(screen.getByText('Jul 2025 - Dec 2025')).toBeInTheDocument()
  })

  it('renders nothing at all for a period with no cost breakdown (e.g. FY2025 Information Document)', () => {
    const { container } = render(<CostWaterfallChart data={waterfall({ available: false })} />)
    expect(container).toBeEmptyDOMElement()
  })
})
