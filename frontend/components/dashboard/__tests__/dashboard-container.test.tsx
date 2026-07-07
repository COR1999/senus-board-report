import { render, screen } from '@testing-library/react'
import { DashboardContainer } from '@/components/dashboard/dashboard-container'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}))

describe('DashboardContainer', () => {
  beforeEach(() => {
    vi.spyOn(dataService, 'getMetrics').mockResolvedValue({
      revenue: { value: 'ANY_REVENUE', change: 10, trend: 'up', history: [1, 2, 3] },
      customers: { value: 'ANY_CUSTOMERS', change: 5, trend: 'up', history: [1, 2, 3] },
      cash: { value: 'ANY_CASH', change: -2, trend: 'down', history: [3, 2, 1] },
      ebitda: { value: 'ANY_EBITDA', change: 3, trend: 'up', history: [] },
      ebitda_margin: { value: 'ANY_EBITDA_MARGIN', change: 1, trend: 'up', history: [] },
      cash_runway: { value: 'ANY_CASH_RUNWAY', change: 1, trend: 'up', history: [] },
      interest_cover: { value: 'ANY_INTEREST_COVER', change: 1, trend: 'up', history: [] },
      roce: { value: 'ANY_ROCE', change: 1, trend: 'up', history: [] },
      bookings: { value: 'ANY_BOOKINGS', change: 0, trend: 'neutral', history: [] },
      current_period: 'Jul 2025 – Dec 2025',
      prior_period: 'Jul 2024 – Dec 2024',
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
})