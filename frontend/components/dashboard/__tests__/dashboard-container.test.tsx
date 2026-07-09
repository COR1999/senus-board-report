import { render, screen, fireEvent } from '@testing-library/react'
import { DashboardContainer } from '@/components/dashboard/dashboard-container'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}))

describe('DashboardContainer', () => {
  beforeEach(() => {
    vi.spyOn(dataService, 'getDashboardPeriods').mockResolvedValue([])
    vi.spyOn(dataService, 'getMetrics').mockResolvedValue({
      revenue: { value: 'ANY_REVENUE', change: 10, trend: 'up', history: [1, 2, 3], available: true },
      customers: { value: 'ANY_CUSTOMERS', change: 5, trend: 'up', history: [1, 2, 3], available: true },
      cash: { value: 'ANY_CASH', change: -2, trend: 'down', history: [3, 2, 1], available: true },
      ebitda: { value: 'ANY_EBITDA', change: 3, trend: 'up', history: [], available: true },
      ebitda_margin: { value: 'ANY_EBITDA_MARGIN', change: 1, trend: 'up', history: [], available: true },
      cash_runway: { value: 'ANY_CASH_RUNWAY', change: 1, trend: 'up', history: [], available: true },
      interest_cover: { value: 'ANY_INTEREST_COVER', change: 1, trend: 'up', history: [], available: true },
      roce: { value: 'ANY_ROCE', change: 1, trend: 'up', history: [], available: true },
      bookings: { value: 'ANY_BOOKINGS', change: 0, trend: 'neutral', history: [], available: true },
      gross_margin: { value: 'ANY_GROSS_MARGIN', change: 1, trend: 'up', history: [], available: true },
      operating_margin: { value: 'ANY_OPERATING_MARGIN', change: 1, trend: 'up', history: [], available: true },
      current_period: 'Jul 2025 – Dec 2025',
      prior_period: 'Jul 2024 – Dec 2024',
      data_extracted_at: '2026-03-19T08:38:00',
      document_id: 1,
    })

    vi.spyOn(dataService, 'getChartData').mockResolvedValue([])

    vi.spyOn(dataService, 'getReports').mockResolvedValue([
      {
        id: 1,
        document_id: 1,
        summary: { company_name: 'ANY_REPORT', reporting_period: 'H1 2025' },
        status: 'completed',
        created_at: '2025-12-31T00:00:00Z',
      },
    ])
  })

  it('receives data and renders dashboard', async () => {
    render(<DashboardContainer />)

    // proves metrics arrived
    expect(await screen.findByText('ANY_REVENUE')).toBeInTheDocument()
    expect(await screen.findByText('ANY_CUSTOMERS')).toBeInTheDocument()

    // proves reports arrived
    expect(await screen.findByText('ANY_REPORT')).toBeInTheDocument()

    // proves dashboard loaded
    expect(await screen.findByText('Executive Dashboard')).toBeInTheDocument()
  })

  it('renders Revenue, EBITDA, Cash, and Customers as large hero cards', async () => {
    render(<DashboardContainer />)

    expect(await screen.findByText('ANY_REVENUE')).toBeInTheDocument()
    expect(await screen.findByText('ANY_EBITDA')).toBeInTheDocument()
    expect(await screen.findByText('ANY_CASH')).toBeInTheDocument()
    expect(await screen.findByText('ANY_CUSTOMERS')).toBeInTheDocument()
  })

  it('renders Bookings and the ratio metrics in the secondary stat strip', async () => {
    render(<DashboardContainer />)

    expect(await screen.findByText('ANY_BOOKINGS')).toBeInTheDocument()
    expect(await screen.findByText('Bookings (new business closed)')).toBeInTheDocument()
    expect(await screen.findByText('ANY_EBITDA_MARGIN')).toBeInTheDocument()
    expect(await screen.findByText('ANY_CASH_RUNWAY')).toBeInTheDocument()
    expect(await screen.findByText('ANY_INTEREST_COVER')).toBeInTheDocument()
    expect(await screen.findByText('ANY_ROCE')).toBeInTheDocument()
  })

  it('does not render the removed mock segment-breakdown chart', async () => {
    render(<DashboardContainer />)

    await screen.findByText('ANY_REVENUE')
    expect(screen.queryByText('Revenue by Segment')).not.toBeInTheDocument()
  })

  it('shows the real reporting period instead of a fabricated cadence claim', async () => {
    render(<DashboardContainer />)

    await screen.findByText('ANY_REVENUE')
    // Revenue/EBITDA/Cash have a real prior-period comparative -- the % change
    // badge conveys the comparison, so only the current period is shown here.
    expect(screen.getAllByText('Jul 2025 – Dec 2025').length).toBeGreaterThan(0)
    // Customers has no real prior comparative -- context only, no comparison claim.
    expect(screen.getByText('as of Jul 2025 – Dec 2025')).toBeInTheDocument()
  })

  it('shows a global "as of" banner stating the currency and extraction date', async () => {
    render(<DashboardContainer />)

    await screen.findByText('ANY_REVENUE')
    expect(await screen.findByText(/All figures in EUR · Data as of/)).toBeInTheDocument()
  })

  it('shows no "as of" banner when there is no data yet', async () => {
    vi.spyOn(dataService, 'getMetrics').mockResolvedValue({
      revenue: { value: 'ANY_REVENUE', change: 0, trend: 'neutral', history: [], available: true },
      customers: { value: '0', change: 0, trend: 'neutral', history: [], available: true },
      cash: { value: 'ANY_CASH', change: 0, trend: 'neutral', history: [], available: true },
      ebitda: { value: 'ANY_EBITDA', change: 0, trend: 'neutral', history: [], available: true },
      ebitda_margin: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      cash_runway: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      interest_cover: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      roce: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      bookings: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      gross_margin: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      operating_margin: { value: 'N/A', change: 0, trend: 'neutral', history: [], available: false },
      current_period: null,
      prior_period: null,
      data_extracted_at: null,
      document_id: null,
    })

    render(<DashboardContainer />)

    await screen.findByText('ANY_REVENUE')
    expect(screen.queryByText(/Data as of/)).not.toBeInTheDocument()
  })

  describe('period selector', () => {
    it('renders no selector when only one (or zero) reporting periods are available', async () => {
      vi.spyOn(dataService, 'getDashboardPeriods').mockResolvedValue([
        { document_id: 1, label: 'HY2026 (Jul 2025 – Dec 2025)' },
      ])

      render(<DashboardContainer />)

      await screen.findByText('ANY_REVENUE')
      expect(screen.queryByRole('combobox', { name: 'Select reporting period' })).not.toBeInTheDocument()
    })

    it('renders a selector with real period labels when multiple periods are available', async () => {
      vi.spyOn(dataService, 'getDashboardPeriods').mockResolvedValue([
        { document_id: 2, label: 'HY2026 (Jul 2025 – Dec 2025)' },
        { document_id: 1, label: 'FY2025 (Jul 2024 – Jun 2025)' },
      ])

      render(<DashboardContainer />)

      await screen.findByText('ANY_REVENUE')
      expect(screen.getByRole('combobox', { name: 'Select reporting period' })).toBeInTheDocument()
      expect(screen.getByText('HY2026 (Jul 2025 – Dec 2025)')).toBeInTheDocument()
    })

    it('refetches metrics with the selected document_id, but never refetches chart data -- the trend chart always shows the whole history', async () => {
      vi.spyOn(dataService, 'getDashboardPeriods').mockResolvedValue([
        { document_id: 2, label: 'HY2026 (Jul 2025 – Dec 2025)' },
        { document_id: 1, label: 'FY2025 (Jul 2024 – Jun 2025)' },
      ])
      const getMetricsSpy = vi.mocked(dataService.getMetrics)
      const getChartDataSpy = vi.mocked(dataService.getChartData)

      render(<DashboardContainer />)

      await screen.findByText('ANY_REVENUE')
      fireEvent.click(screen.getByRole('combobox', { name: 'Select reporting period' }))
      fireEvent.click(await screen.findByRole('option', { name: 'FY2025 (Jul 2024 – Jun 2025)' }))

      await screen.findByText('ANY_REVENUE')
      expect(getMetricsSpy).toHaveBeenCalledWith(1)
      expect(getChartDataSpy).toHaveBeenCalledWith()
    })
  })
})