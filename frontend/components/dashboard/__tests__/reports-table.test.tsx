import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ReportsTable } from '@/components/dashboard/reports-table'
import * as dataService from '@/lib/data-service'
import type { Report } from '@/lib/data-service'
import { describe, it, expect, vi } from 'vitest'

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

  it('filters by status', async () => {
    render(<ReportsTable reports={reports} />)

    fireEvent.click(screen.getByRole('combobox', { name: 'Filter by status' }))
    fireEvent.click(await screen.findByRole('option', { name: 'Failed' }))

    expect(await screen.findByText('Document #103')).toBeInTheDocument()
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

  it('capitalizes the status badge text', () => {
    render(<ReportsTable reports={reports} />)
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('Generating')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('shows a disabled year/month filter button noting it is coming soon', () => {
    render(<ReportsTable reports={reports} />)
    expect(screen.getByRole('button', { name: /filter by period/i })).toBeDisabled()
  })

  it('calls regenerateReport and onRegenerated when the regenerate button is clicked', async () => {
    const regenerateSpy = vi.spyOn(dataService, 'regenerateReport').mockResolvedValue(reports[0])
    const onRegenerated = vi.fn()

    render(<ReportsTable reports={reports} onRegenerated={onRegenerated} />)
    fireEvent.click(screen.getAllByTitle('Regenerate report')[0])

    await waitFor(() => expect(regenerateSpy).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onRegenerated).toHaveBeenCalled())
  })

  it('does not call onRegenerated when regeneration fails', async () => {
    vi.spyOn(dataService, 'regenerateReport').mockRejectedValue(new Error('boom'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const onRegenerated = vi.fn()

    render(<ReportsTable reports={reports} onRegenerated={onRegenerated} />)
    fireEvent.click(screen.getAllByTitle('Regenerate report')[0])

    await waitFor(() => expect(dataService.regenerateReport).toHaveBeenCalled())
    expect(onRegenerated).not.toHaveBeenCalled()
  })
})
