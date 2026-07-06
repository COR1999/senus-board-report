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
})
