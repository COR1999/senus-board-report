import { render, screen } from '@testing-library/react'
import { RecentReports } from '@/components/dashboard/recent-reports'
import { describe, it, expect } from 'vitest'
import type { Report } from '@/lib/data-service'

function report(overrides: Partial<Report> & { id: number; created_at: string }): Report {
  return {
    document_id: overrides.id,
    summary: { company_name: 'Senus PLC', reporting_period: 'FY2025' },
    status: 'completed',
    ...overrides,
  }
}

describe('RecentReports', () => {
  it('shows only the most recent `limit` reports, newest first', () => {
    const reports = [
      report({ id: 1, created_at: '2025-01-01T00:00:00Z' }),
      report({ id: 2, created_at: '2025-06-01T00:00:00Z' }),
      report({ id: 3, created_at: '2025-03-01T00:00:00Z' }),
      report({ id: 4, created_at: '2025-12-01T00:00:00Z' }),
    ]
    render(<RecentReports reports={reports} limit={2} />)

    const names = screen.getAllByText('Senus PLC')
    expect(names).toHaveLength(2)
  })

  it('links to the full reports page, not a search/filter/export table', () => {
    render(<RecentReports reports={[report({ id: 1, created_at: '2025-01-01T00:00:00Z' })]} />)

    const link = screen.getByRole('link', { name: 'View all' })
    expect(link).toHaveAttribute('href', '/reports')
    expect(screen.queryByPlaceholderText('Search reports...')).not.toBeInTheDocument()
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument()
  })

  it('falls back to a document-number name when no company name was extracted', () => {
    render(
      <RecentReports
        reports={[report({ id: 7, created_at: '2025-01-01T00:00:00Z', summary: null })]}
      />
    )
    expect(screen.getByText('Document #7')).toBeInTheDocument()
  })

  it('shows an empty state with zero reports', () => {
    render(<RecentReports reports={[]} />)
    expect(screen.getByText('No reports available')).toBeInTheDocument()
  })
})
