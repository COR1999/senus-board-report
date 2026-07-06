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
    })

    vi.spyOn(dataService, 'getChartData').mockResolvedValue([])

    vi.spyOn(dataService, 'getSegmentBreakdown').mockResolvedValue([
      { segment: 'Corporate', value: 100, percentage: 100 },
    ])

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

  it('renders the Cash, Solvency & Returns KPI section', async () => {
    render(<DashboardContainer />)

    expect(await screen.findByText('Cash, Solvency & Returns')).toBeInTheDocument()
    expect(await screen.findByText('ANY_EBITDA_MARGIN')).toBeInTheDocument()
    expect(await screen.findByText('ANY_CASH_RUNWAY')).toBeInTheDocument()
    expect(await screen.findByText('ANY_INTEREST_COVER')).toBeInTheDocument()
    expect(await screen.findByText('ANY_ROCE')).toBeInTheDocument()
  })
})