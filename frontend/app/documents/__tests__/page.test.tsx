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
})
