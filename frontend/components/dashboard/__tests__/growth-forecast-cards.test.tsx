import { render, screen } from '@testing-library/react'
import { GrowthForecastCards } from '@/components/dashboard/growth-forecast-cards'
import { describe, it, expect } from 'vitest'
import type { ChartDataPoint } from '@/lib/data-service'

function point(overrides: Partial<ChartDataPoint> & { period: string }): ChartDataPoint {
  return { revenue: null, ebitda: null, cash: null, document_id: null, cadence_months: null, ...overrides }
}

describe('GrowthForecastCards', () => {
  it('renders the four forecast stats projected from the latest real revenue', () => {
    render(<GrowthForecastCards chartData={[point({ period: 'FY2025', revenue: 837_000 })]} />)

    expect(screen.getByText('Growth to 2030')).toBeInTheDocument()
    expect(screen.getByText('Projected Revenue 2030')).toBeInTheDocument()
    expect(screen.getByText('Target CAGR')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('Growth Multiple')).toBeInTheDocument()
    expect(screen.getByText('Progress to Target')).toBeInTheDocument()
  })

  it('renders a progress bar reflecting current-vs-target', () => {
    render(<GrowthForecastCards chartData={[point({ period: 'FY2025', revenue: 837_000 })]} />)

    const bar = screen.getByRole('progressbar', { name: /Progress toward 2030 revenue target/ })
    expect(bar).toBeInTheDocument()
    expect(Number(bar.getAttribute('aria-valuenow'))).toBeGreaterThan(0)
    expect(Number(bar.getAttribute('aria-valuenow'))).toBeLessThan(100)
  })

  it('renders nothing without a real revenue baseline to project from', () => {
    const { container } = render(<GrowthForecastCards chartData={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when every point is missing both revenue and a parseable year', () => {
    const { container } = render(
      <GrowthForecastCards chartData={[point({ period: 'Next Report 1', revenue: null })]} />
    )
    expect(container).toBeEmptyDOMElement()
  })
})
