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
      { id: 1, filename: 'ANY_DOCUMENT.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: null, superseded_by_document_id: null },
    ])
    // Otherwise every test in this file makes a real network call (the
    // hook has no mock/fallback data path like getDocuments) -- default to
    // "nothing new" so only the tests below that care about the banner
    // override this.
    vi.spyOn(dataService, 'getAvailableExternalFilings').mockResolvedValue([])
    vi.spyOn(dataService, 'getHiddenExternalFilings').mockResolvedValue([])
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

  it('shows a muted "Pending Review" tag for a needs_review document', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 1, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
        created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'needs_review',
        superseded_by_document_id: null,
      },
    ])
    render(<DocumentsPage />)
    expect(await screen.findByText('Pending Review')).toBeInTheDocument()
  })

  it('shows no confidence tag for an auto-accepted document', async () => {
    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')
    expect(screen.queryByText('Pending Review')).not.toBeInTheDocument()
  })

  it('filters the list by filename search', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      { id: 1, filename: 'senus-filing.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: null, superseded_by_document_id: null },
      { id: 2, filename: 'other-report.pdf', file_size: 2048, status: 'completed', created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: null, superseded_by_document_id: null },
    ])

    render(<DocumentsPage />)
    await screen.findByText('senus-filing.pdf')

    fireEvent.change(screen.getByLabelText('Search documents'), { target: { value: 'senus' } })

    expect(screen.getByText('senus-filing.pdf')).toBeInTheDocument()
    expect(screen.queryByText('other-report.pdf')).not.toBeInTheDocument()
  })

  it('filters by period (year/month of created_at)', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      { id: 1, filename: 'december.pdf', file_size: 1024, status: 'completed', created_at: '2025-12-15T12:00:00Z', extraction_confidence_tier: null, superseded_by_document_id: null },
      { id: 2, filename: 'june.pdf', file_size: 1024, status: 'completed', created_at: '2025-06-15T12:00:00Z', extraction_confidence_tier: null, superseded_by_document_id: null },
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

  it('downloads a document via the download button', async () => {
    const downloadSpy = vi.spyOn(dataService, 'downloadDocument').mockResolvedValue(undefined)

    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    fireEvent.click(screen.getByRole('button', { name: /download any_document\.pdf/i }))

    await waitFor(() => expect(downloadSpy).toHaveBeenCalledWith(1, 'ANY_DOCUMENT.pdf'))
  })

  it('shows the backend\'s specific error message when a download fails', async () => {
    // Real production gap: a plain <a href download> gave the browser
    // nothing to show when the backend 404s (Railway's filesystem isn't
    // persistent across redeploys) -- the fetch-and-blob approach surfaces
    // the actual detail message instead of a silently dead button.
    vi.spyOn(dataService, 'downloadDocument').mockRejectedValue(
      new Error("The original PDF is no longer available on the server (uploads aren't yet persisted across deploys).")
    )

    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    fireEvent.click(screen.getByRole('button', { name: /download any_document\.pdf/i }))

    expect(await screen.findByText(/no longer available on the server/i)).toBeInTheDocument()
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
      extraction_confidence_tier: null,
      superseded_by_document_id: null,
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

  it('hides a filing and refreshes both the available and hidden lists', async () => {
    vi.spyOn(dataService, 'getAvailableExternalFilings').mockResolvedValue([
      { attachment_id: 'agm-notice-id', file_name: 'Senus_Circular_Notice of AGM 2026', file_size: 239_000, published_date: '2026-06-05' },
    ])
    const hideSpy = vi.spyOn(dataService, 'hideExternalFiling').mockResolvedValue(undefined)

    render(<DocumentsPage />)
    const hideButton = await screen.findByRole('button', { name: /mark senus_circular_notice of agm 2026 as out of scope/i })
    fireEvent.click(hideButton)

    await waitFor(() => expect(hideSpy).toHaveBeenCalledWith('agm-notice-id'))
    // onSuccess refetches both lists -- once on mount, once after hiding.
    await waitFor(() => expect(dataService.getAvailableExternalFilings).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(dataService.getHiddenExternalFilings).toHaveBeenCalledTimes(2))
  })

  it('shows an "Out of scope" section listing hidden filings', async () => {
    vi.spyOn(dataService, 'getHiddenExternalFilings').mockResolvedValue([
      { attachment_id: 'agm-notice-id', file_name: 'Senus_Circular_Notice of AGM 2026', file_size: 239_000, published_date: '2026-06-05' },
    ])

    render(<DocumentsPage />)

    expect(await screen.findByText('Out of scope (1)')).toBeInTheDocument()
    expect(screen.getByText('Senus_Circular_Notice of AGM 2026')).toBeInTheDocument()
  })

  it('shows a "Merged" tag naming the target document for a superseded document', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 37, filename: 'ADF Farm Solutions Consolidated Financial Statements.pdf', file_size: 1024,
        status: 'completed', created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'auto_accept',
        superseded_by_document_id: 100,
      },
      {
        id: 100, filename: 'FY2025 (merged: ADF Farm Solutions + Information Document)', file_size: 1024,
        status: 'completed', created_at: '2026-01-01T00:00:00Z', extraction_confidence_tier: 'auto_accept',
        superseded_by_document_id: null,
      },
    ])
    render(<DocumentsPage />)

    const mergedTag = await screen.findByText('Merged')
    expect(mergedTag).toHaveAttribute(
      'title',
      expect.stringContaining('FY2025 (merged: ADF Farm Solutions + Information Document)')
    )
  })

  it('does not show the "Out of scope" section when nothing is hidden', async () => {
    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    expect(screen.queryByText(/Out of scope/)).not.toBeInTheDocument()
  })

  it('restores a hidden filing and refreshes both lists', async () => {
    vi.spyOn(dataService, 'getHiddenExternalFilings').mockResolvedValue([
      { attachment_id: 'agm-notice-id', file_name: 'Senus_Circular_Notice of AGM 2026', file_size: 239_000, published_date: '2026-06-05' },
    ])
    const unhideSpy = vi.spyOn(dataService, 'unhideExternalFiling').mockResolvedValue(undefined)

    render(<DocumentsPage />)
    const restoreButton = await screen.findByRole('button', { name: /restore/i })
    fireEvent.click(restoreButton)

    await waitFor(() => expect(unhideSpy).toHaveBeenCalledWith('agm-notice-id'))
    await waitFor(() => expect(dataService.getAvailableExternalFilings).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(dataService.getHiddenExternalFilings).toHaveBeenCalledTimes(2))
  })

  it('does not show a Review button for a document with no confidence tier', async () => {
    render(<DocumentsPage />)
    await screen.findByText('ANY_DOCUMENT.pdf')

    expect(screen.queryByRole('button', { name: /review ANY_DOCUMENT\.pdf/i })).not.toBeInTheDocument()
  })

  it('opens the review sheet for a needs_review document and shows its extracted values', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 5, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
        created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'needs_review',
        superseded_by_document_id: null,
      },
    ])
    vi.spyOn(dataService, 'getDocument').mockResolvedValue({
      id: 5, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
      created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'needs_review',
      superseded_by_document_id: null,
      financial_metrics: {
        revenue: null, customers: null, cash: 120_000, ebitda: null,
        gross_margin: null, operating_margin: null,
        extraction_confidence: 55, extraction_confidence_tier: 'needs_review',
        extraction_confidence_reasons: null,
      },
    })

    render(<DocumentsPage />)
    const reviewButton = await screen.findByRole('button', { name: /review shaky-extraction\.pdf/i })
    fireEvent.click(reviewButton)

    expect(await screen.findByText('€120K')).toBeInTheDocument()
    expect(screen.getByText('55% confidence')).toBeInTheDocument()
    expect(screen.getAllByText('Not reported').length).toBeGreaterThan(0)
  })

  it('approves a document from the review sheet and refreshes the document list', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 5, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
        created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'needs_review',
        superseded_by_document_id: null,
      },
    ])
    vi.spyOn(dataService, 'getDocument').mockResolvedValue({
      id: 5, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
      created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'needs_review',
      superseded_by_document_id: null,
      financial_metrics: {
        revenue: null, customers: null, cash: 120_000, ebitda: null,
        gross_margin: null, operating_margin: null,
        extraction_confidence: 55, extraction_confidence_tier: 'needs_review',
        extraction_confidence_reasons: null,
      },
    })
    const approveSpy = vi.spyOn(dataService, 'approveDocument').mockResolvedValue({
      id: 5, filename: 'shaky-extraction.pdf', file_size: 1024, status: 'completed',
      created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'auto_accept',
      superseded_by_document_id: null,
      financial_metrics: null,
    })

    render(<DocumentsPage />)
    fireEvent.click(await screen.findByRole('button', { name: /review shaky-extraction\.pdf/i }))
    await screen.findByText('€120K')

    fireEvent.click(screen.getByRole('button', { name: /approve for dashboard/i }))

    await waitFor(() => expect(approveSpy).toHaveBeenCalledWith(5))
    // onApproved refetches the document list -- once on mount, once after approve.
    await waitFor(() => expect(dataService.getDocuments).toHaveBeenCalledTimes(2))
  })

  it('shows a destructive "Rejected" tag for a rejected document', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 6, filename: 'agm-notice.pdf', file_size: 1024, status: 'completed',
        created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'rejected',
        superseded_by_document_id: null,
      },
    ])
    render(<DocumentsPage />)
    expect(await screen.findByText('Rejected')).toBeInTheDocument()
  })

  it('opens the review sheet for a rejected document view-only, with no Approve button', async () => {
    vi.spyOn(dataService, 'getDocuments').mockResolvedValue([
      {
        id: 6, filename: 'agm-notice.pdf', file_size: 1024, status: 'completed',
        created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'rejected',
        superseded_by_document_id: null,
      },
    ])
    vi.spyOn(dataService, 'getDocument').mockResolvedValue({
      id: 6, filename: 'agm-notice.pdf', file_size: 1024, status: 'completed',
      created_at: '2025-12-31T00:00:00Z', extraction_confidence_tier: 'rejected',
      superseded_by_document_id: null,
      financial_metrics: {
        revenue: null, customers: null, cash: null, ebitda: null,
        gross_margin: null, operating_margin: null,
        extraction_confidence: 0, extraction_confidence_tier: 'rejected',
        extraction_confidence_reasons: ['No recognized financial-statement section was found in this document.'],
      },
    })
    const approveSpy = vi.spyOn(dataService, 'approveDocument')

    render(<DocumentsPage />)
    fireEvent.click(await screen.findByRole('button', { name: /review agm-notice\.pdf/i }))

    expect(await screen.findByText('No recognized financial-statement section was found in this document.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve for dashboard/i })).not.toBeInTheDocument()
    expect(approveSpy).not.toHaveBeenCalled()
  })
})
