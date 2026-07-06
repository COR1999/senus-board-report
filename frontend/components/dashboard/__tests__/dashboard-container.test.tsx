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
      revenue: { value: 'ANY_REVENUE', change: 10, trend: 'up' },
      customers: { value: 'ANY_CUSTOMERS', change: 5, trend: 'up' },
      cash: { value: 'ANY_CASH', change: -2, trend: 'down' },
      ebitda: { value: 'ANY_EBITDA', change: 3, trend: 'up' },
    })

    vi.spyOn(dataService, 'getChartData').mockResolvedValue([])

    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue([
      { text: 'ANY_INSIGHT_TEXT', type: 'positive' },
    ])

    vi.spyOn(dataService, 'getReports').mockResolvedValue([
      { id: 1, name: 'ANY_REPORT', date: 'x', status: 'completed' },
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
})