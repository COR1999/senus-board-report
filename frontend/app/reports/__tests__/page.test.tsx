import { render, screen } from '@testing-library/react'
import ReportsPage from '@/app/reports/page'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/reports',
}))

describe('ReportsPage', () => {
  beforeEach(() => {
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

  it('fetches and renders reports', async () => {
    render(<ReportsPage />)
    expect(await screen.findByText('ANY_REPORT')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Reports' })).toBeInTheDocument()
  })
})
