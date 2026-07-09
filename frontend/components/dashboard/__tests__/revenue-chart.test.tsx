import { render, screen, fireEvent } from '@testing-library/react'
import { RevenueChart, buildChartRows, cadenceBucket, determineRenderMode } from '@/components/dashboard/revenue-chart'
import { describe, it, expect } from 'vitest'
import type { ChartDataPoint } from '@/lib/data-service'

const mockData = [
  { period: 'Jan', revenue: 100, ebitda: -10, cash: 50, document_id: 1, cadence_months: 12 },
  { period: 'Feb', revenue: 200, ebitda: -5, cash: 60, document_id: 2, cadence_months: 12 },
  { period: 'Mar', revenue: 300, ebitda: 5, cash: 70, document_id: 3, cadence_months: 12 },
]

describe('RevenueChart', () => {
  it('renders with revenue data', () => {
    const { container } = render(<RevenueChart data={mockData} />)

    expect(container.firstChild).toBeInTheDocument()
    expect(screen.getByText('Revenue Trend')).toBeInTheDocument()
  })

  it('shows a forecast toggle and does not crash when switched on', async () => {
    const { container } = render(<RevenueChart data={mockData} />)

    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)

    expect(container.firstChild).toBeInTheDocument()
  })

  it('swaps to EBITDA and keeps the forecast toggle available', () => {
    const { container } = render(<RevenueChart data={mockData} />)

    fireEvent.click(screen.getByRole('button', { name: 'EBITDA' }))
    expect(screen.getByText('EBITDA Trend')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('switch'))
    expect(container.firstChild).toBeInTheDocument()
  })

  it('swaps to Cash and back to Revenue', () => {
    render(<RevenueChart data={mockData} />)

    fireEvent.click(screen.getByRole('button', { name: 'Cash' }))
    expect(screen.getByText('Cash Trend')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Revenue' }))
    expect(screen.getByText('Revenue Trend')).toBeInTheDocument()
  })

  it('does not crash on mixed HY/FY data (3+ FY points) with a selected point and forecast on', () => {
    const mixedData = [
      { period: 'FY2023', revenue: 600_000, ebitda: -80_000, cash: 300_000, document_id: 9, cadence_months: 12 },
      { period: 'FY2024', revenue: 700_000, ebitda: -50_000, cash: 400_000, document_id: 10, cadence_months: 12 },
      { period: 'HY2025', revenue: 350_000, ebitda: -20_000, cash: 500_000, document_id: 11, cadence_months: 6 },
      { period: 'FY2025', revenue: 836_991, ebitda: -613_313, cash: 140_135, document_id: 12, cadence_months: 12 },
    ]
    const { container } = render(<RevenueChart data={mixedData} selectedDocumentId={12} />)

    fireEvent.click(screen.getByRole('switch'))

    expect(container.firstChild).toBeInTheDocument()
  })

  describe('point-count-aware render modes', () => {
    it('shows a stat callout per cadence, no forecast toggle, with exactly one real point each', () => {
      const onePerCadence = [
        { period: 'FY2025', revenue: 836_991, ebitda: -613_313, cash: 140_135, document_id: 1, cadence_months: 12 },
        { period: 'HY2026', revenue: 355_000, ebitda: -50_000, cash: 140_135, document_id: 2, cadence_months: 6 },
      ]
      render(<RevenueChart data={onePerCadence} />)

      expect(screen.getByText('Full Year')).toBeInTheDocument()
      expect(screen.getByText('Half Year')).toBeInTheDocument()
      expect(screen.getByText('€837K')).toBeInTheDocument()
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    })

    it('renders without a forecast toggle, with exactly two real points in the fullest cadence', () => {
      // ResponsiveContainer reports zero width under jsdom and never renders
      // Recharts' actual SVG children (see buildChartRows' own docstring on
      // why chart-shaping logic is tested as a pure function instead) -- this
      // only asserts the surrounding chrome, the same pattern every other
      // render-mode test in this file follows.
      const twoFyPoints = [
        { period: 'FY2023', revenue: 600_000, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
        { period: 'FY2024', revenue: 700_000, ebitda: null, cash: null, document_id: 2, cadence_months: 12 },
      ]
      const { container } = render(<RevenueChart data={twoFyPoints} />)

      expect(container.firstChild).toBeInTheDocument()
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
      expect(screen.queryByText(/No revenue data yet/)).not.toBeInTheDocument()
    })

    it('shows a placeholder, not an empty chart, with zero real points', () => {
      render(<RevenueChart data={[]} />)

      expect(screen.getByText(/No revenue data yet/)).toBeInTheDocument()
      expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    })

    it('still shows the forecast toggle once a cadence reaches 3+ real points', () => {
      render(<RevenueChart data={mockData} />)
      expect(screen.getByRole('switch')).toBeInTheDocument()
    })
  })
})

describe('determineRenderMode', () => {
  it('returns "empty" for no data', () => {
    expect(determineRenderMode([])).toBe('empty')
  })

  it('returns "stat" when the fullest cadence bucket has exactly one point', () => {
    expect(
      determineRenderMode([
        { period: 'FY2025', revenue: 1, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
      ])
    ).toBe('stat')
  })

  it('returns "bars" when the fullest cadence bucket has exactly two points', () => {
    expect(
      determineRenderMode([
        { period: 'FY2023', revenue: 1, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
        { period: 'FY2024', revenue: 2, ebitda: null, cash: null, document_id: 2, cadence_months: 12 },
      ])
    ).toBe('bars')
  })

  it('returns "line" once any cadence bucket reaches three or more points', () => {
    expect(determineRenderMode(mockData)).toBe('line')
  })
})

describe('cadenceBucket', () => {
  it('buckets 6 months or fewer as half-year', () => {
    expect(cadenceBucket(6)).toBe('hy')
    expect(cadenceBucket(3)).toBe('hy')
  })

  it('buckets 9 months or more as full-year', () => {
    expect(cadenceBucket(12)).toBe('fy')
    expect(cadenceBucket(9)).toBe('fy')
  })

  it('buckets an undeterminable or in-between cadence as other, not guessed into either line', () => {
    expect(cadenceBucket(null)).toBe('other')
    expect(cadenceBucket(7)).toBe('other')
    expect(cadenceBucket(8)).toBe('other')
  })
})

describe('buildChartRows', () => {
  const mixed: ChartDataPoint[] = [
    { period: 'FY2023', revenue: 600_000, ebitda: -80_000, cash: 300_000, document_id: 1, cadence_months: 12 },
    { period: 'HY2024', revenue: 300_000, ebitda: -40_000, cash: 350_000, document_id: 2, cadence_months: 6 },
    { period: 'FY2024', revenue: 700_000, ebitda: -50_000, cash: 400_000, document_id: 3, cadence_months: 12 },
    { period: 'HY2025', revenue: 354_813, ebitda: -20_000, cash: 500_000, document_id: 4, cadence_months: 6 },
  ]

  it('splits points into separate fy/hy series rather than one connected line', () => {
    const rows = buildChartRows(mixed, 'revenue', false)

    expect(rows.map((r) => r.fy)).toEqual([600_000, null, 700_000, null])
    expect(rows.map((r) => r.hy)).toEqual([null, 300_000, null, 354_813])
  })

  it('routes an undeterminable-cadence point to "other", not fy or hy', () => {
    const withUnknown: ChartDataPoint[] = [
      ...mixed,
      { period: 'Unknown', revenue: 100, ebitda: null, cash: null, document_id: 5, cadence_months: null },
    ]
    const rows = buildChartRows(withUnknown, 'revenue', false)
    const last = rows[rows.length - 1]

    expect(last.other).toBe(100)
    expect(last.fy).toBeNull()
    expect(last.hy).toBeNull()
  })

  it('adds no forecast rows when showForecast is false', () => {
    const rows = buildChartRows(mixed, 'revenue', false)
    expect(rows).toHaveLength(mixed.length)
  })

  it('projects fy and hy forecasts independently and merges them into the same trailing rows by index', () => {
    const rows = buildChartRows(mixed, 'revenue', true)

    // 4 real rows + 3 forecast rows (FORECAST_PERIODS)
    expect(rows).toHaveLength(7)
    const forecastRows = rows.slice(4)

    // Both cadence forecasts land on the SAME rows (by index), not appended
    // as separate trailing series -- this is what lets a viewer compare a
    // half-year run-rate projection against the full-year's own projection
    // at the same point on the x-axis.
    for (const row of forecastRows) {
      expect(row.fy_forecast).not.toBeNull()
      expect(row.hy_forecast).not.toBeNull()
      expect(row.fy).toBeNull()
      expect(row.hy).toBeNull()
    }

    // fy history is a clean rise (600k -> 700k), so the projection continues upward
    expect(forecastRows[0].fy_forecast).toBeGreaterThan(700_000)
    // hy history falls (300k -> 354,813 is actually a rise) -- just assert it's a real number, not the exact trend direction
    expect(typeof forecastRows[0].hy_forecast).toBe('number')
  })

  it('hands off the last real point of each cadence into its own _forecast key so the lines visually join with no gap', () => {
    const rows = buildChartRows(mixed, 'revenue', true)

    // Last FY row (index 2) and last HY row (index 3) each carry their own
    // real value under the matching _forecast key -- the solid and dashed
    // segments share one point instead of a visible break.
    expect(rows[2].fy_forecast).toBe(700_000)
    expect(rows[3].hy_forecast).toBe(354_813)
  })

  it('produces no forecast rows at all when there are fewer than 2 points in every cadence', () => {
    const singlePointPerCadence: ChartDataPoint[] = [
      { period: 'FY2024', revenue: 700_000, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
      { period: 'HY2025', revenue: 300_000, ebitda: null, cash: null, document_id: 2, cadence_months: 6 },
    ]
    const rows = buildChartRows(singlePointPerCadence, 'revenue', true)

    expect(rows).toHaveLength(2)
  })
})
