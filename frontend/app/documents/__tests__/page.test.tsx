import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import DocumentsPage from '@/app/documents/page'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/documents',
}))

describe('DocumentsPage', () => {
  beforeEach(() => {
    // vitest.config.ts doesn't set clearMocks, so spy call history otherwise
    // leaks across tests in this file -- reset before each test rather than
    // rely on shared state.
    vi.restoreAllMocks()
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      { id: 1, filename: 'ANY_DOCUMENT.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-31T00:00:00Z' },
    ])
    // Otherwise every test in this file makes a real network call (the
    // hook has no mock/fallback data path like getDocuments) -- default to
    // "nothing new" so only the tests below that care about the banner
    // override this.
    vi.spyOn(dataService, 'getAvailableExternalFilings').mockResolvedValue([])
  })

  it('fetches and renders documents', async () => {
    render(<DocumentsPage />)
    expect(await screen.findByText('ANY_DOCUMENT.pdf')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Documents' })).toBeInTheDocument()
  })

  it('shows an empty state when there are no documents', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([])
    render(<DocumentsPage />)
    expect(await screen.findByText('No documents uploaded yet')).toBeInTheDocument()
  })

  it('deletes a document and refreshes the list after confirming', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const deleteSpy = vi.spyOn(dataService, 'deleteDocument').mockResolvedValue(undefined)

    render(<DocumentsPage />)
    const deleteButton = await screen.findByRole('button', { name: /delete ANY_DOCUMENT\.pdf/i })
    fireEvent.click(deleteButton)

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(1))
    // refresh() calls getDocuments() again -- once on mount, once after delete.
    await waitFor(() => expect(dataService.getDocuments).toHaveBeenCalledTimes(2))
  })

  it('does not delete when the confirmation is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const deleteSpy = vi.spyOn(dataService, 'deleteDocument').mockResolvedValue(undefined)

    render(<DocumentsPage />)
    const deleteButton = await screen.findByRole('button', { name: /delete ANY_DOCUMENT\.pdf/i })
    fireEvent.click(deleteButton)

    expect(deleteSpy).not.toHaveBeenCalled()
  })

  it('capitalizes the status and shows a formatted file size', async () => {
    render(<DocumentsPage />)
    expect(await screen.findByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('1 KB')).toBeInTheDocument()
  })

  it('filters the list by filename search', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      { id: 1, filename: 'senus-filing.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-31T00:00:00Z' },
      { id: 2, filename: 'other-report.pdf', file_size: 2048, status: 'completed', created_at: '2025-12-31T00:00:00Z' },
    ])

    render(<DocumentsPage />)
    await screen.findByText('senus-filing.pdf')

    fireEvent.change(screen.getByLabelText('Search documents'), { target: { value: 'senus' } })

    expect(screen.getByText('senus-filing.pdf')).toBeInTheDocument()
    expect(screen.queryByText('other-report.pdf')).not.toBeInTheDocument()
  })

  it('filters by period (year/month of created_at)', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      { id: 1, filename: 'december.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-15T12:00:00Z' },
      { id: 2, filename: 'june.pdf', file_size: 1024, status: 'completed', created_at: '2025-06-15T12:00:00Z' },
    ])

    render(<DocumentsPage />)
    await screen.findByText('december.pdf')

    fireEvent.click(screen.getByRole('combobox', { name: 'Filter by period' }))
    fireEvent.click(await screen.findByRole('option', { name: 'December 2025' }))

    expect(await screen.findByText('december.pdf')).toBeInTheDocument()
    expect(screen.queryByText('june.pdf')).not.toBeInTheDocument()
  })

  it('rejects an oversized file before uploading, with no network call', async () => {
    const uploadSpy = vi.spyOn(dataService, 'uploadPDF')

    const { container } = render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement
    const oversizedFile = new File(['x'.repeat(10)], 'huge.pdf', { type: 'application/pdf' })
    Object.defineProperty(oversizedFile, 'size', { value: 21 * 1024 * 1024 })

    fireEvent.change(fileInput, { target: { files: [oversizedFile] } })

    expect(await screen.findByText(/huge\.pdf.*over the 20MB upload limit/i)).toBeInTheDocument()
    expect(uploadSpy).not.toHaveBeenCalled()
  })

  it('links the download button to the real file download URL', async () => {
    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    const downloadLink = screen.getByRole('link', { name: /download any_document\.pdf/i })
    expect(downloadLink).toHaveAttribute('href', dataService.getDocumentFileUrl(1))
  })

  it('shows a quiet "no new filings" message with a manual check when none are available', async () => {
    render(<DocumentsPage />)
    expect(await screen.findByText(/No new filings from Senus/i)).toBeInTheDocument()
  })

  it('shows a banner listing filings available from the investor relations API', async () => {
    vi.spyOn(dataService, 'getAvailableExternalFilings').mockResolvedValue([
      { attachment_id: 'info-doc-id', file_name: 'Senus PLC Information Document', file_size: 1_056_649, published_date: '2025-12-01' },
    ])

    render(<DocumentsPage />)

    expect(await screen.findByText("1 new filing available from Senus's investor relations page")).toBeInTheDocument()
    expect(screen.getByText('Senus PLC Information Document')).toBeInTheDocument()
  })

  it('imports a filing and refreshes both the documents and available-filings lists', async () => {
    vi.spyOn(dataService, 'getAvailableExternalFilings').mockResolvedValue([
      { attachment_id: 'info-doc-id', file_name: 'Senus PLC Information Document', file_size: 1_056_649, published_date: '2025-12-01' },
    ])
    const importSpy = vi.spyOn(dataService, 'importExternalFiling').mockResolvedValue({
      id: 2,
      filename: 'Senus PLC Information Document.pdf',
      file_size: 1_056_649,
      status: 'completed',
      created_at: '2026-07-08T00:00:00Z',
    })

    render(<DocumentsPage />)
    const importButton = await screen.findByRole('button', { name: /^import$/i })
    fireEvent.click(importButton)

    await waitFor(() => expect(importSpy).toHaveBeenCalledWith('info-doc-id'))
    // onSuccess refetches both lists -- once on mount, once after import.
    await waitFor(() => expect(dataService.getDocuments).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(dataService.getAvailableExternalFilings).toHaveBeenCalledTimes(2))
  })

  it('re-checks the investor relations API when "Check now" is clicked', async () => {
    render(<DocumentsPage />)
    const checkNowButton = await screen.findByRole('button', { name: /check now/i })

    fireEvent.click(checkNowButton)

    await waitFor(() => expect(dataService.getAvailableExternalFilings).toHaveBeenCalledTimes(2))
  })
})
