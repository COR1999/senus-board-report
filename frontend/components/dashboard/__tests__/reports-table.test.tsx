import { render, screen, fireEvent } from '@testing-library/react'
import { ReportsTable } from '@/components/dashboard/reports-table'
import type { Report } from '@/lib/data-service'
import { describe, it, expect } from 'vitest'

const reports: Report[] = [
  {
    id: 1,
    document_id: 101,
    summary: { company_name: 'Senus PLC', reporting_period: 'H1 2025' },
    status: 'completed',
    created_at: '2025-12-31T00:00:00Z',
  },
  {
    id: 2,
    document_id: 102,
    summary: { company_name: 'Acme Corp', reporting_period: 'Q3 2025' },
    status: 'generating',
    created_at: '2025-09-30T00:00:00Z',
  },
  {
    id: 3,
    document_id: 103,
    summary: null,
    status: 'failed',
    created_at: '2025-06-30T00:00:00Z',
  },
]

describe('ReportsTable', () => {
  it('renders without crashing', () => {
    const { container } = render(<ReportsTable />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('renders a display name for each report, falling back to Document #id when summary is null', () => {
    render(<ReportsTable reports={reports} />)
    expect(screen.getByText('Senus PLC')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('Document #103')).toBeInTheDocument()
  })

  it('filters by search text', () => {
    render(<ReportsTable reports={reports} />)
    fireEvent.change(screen.getByLabelText('Search reports'), { target: { value: 'acme' } })

    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.queryByText('Senus PLC')).not.toBeInTheDocument()
  })

  it('filters by status', () => {
    render(<ReportsTable reports={reports} />)
    fireEvent.change(screen.getByLabelText('Filter by status'), { target: { value: 'failed' } })

    expect(screen.getByText('Document #103')).toBeInTheDocument()
    expect(screen.queryByText('Senus PLC')).not.toBeInTheDocument()
  })

  it('shows a distinct empty state when filters exclude everything, vs. no data at all', () => {
    const { rerender } = render(<ReportsTable reports={[]} />)
    expect(screen.getByText('No reports available')).toBeInTheDocument()

    rerender(<ReportsTable reports={reports} />)
    fireEvent.change(screen.getByLabelText('Search reports'), { target: { value: 'no-such-report' } })
    expect(screen.getByText('No reports match your filters')).toBeInTheDocument()
  })

  it('disables the CSV export button when there is nothing to export', () => {
    render(<ReportsTable reports={[]} />)
    expect(screen.getByRole('button', { name: /export csv/i })).toBeDisabled()
  })
})
