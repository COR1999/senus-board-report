import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as dataService from '@/lib/data-service'
import {
  useUploadDocument,
  useDeleteDocument,
  useRegenerateReport,
  useImportExternalFiling,
  useApproveDocument,
} from '@/lib/hooks/use-mutations'

describe('useUploadDocument', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('calls onSuccess and clears uploading/error on a successful upload', async () => {
    vi.spyOn(dataService, 'uploadPDF').mockResolvedValue({ id: '1', message: 'ok' })
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useUploadDocument(onSuccess))

    act(() => {
      result.current.upload(new File(['x'], 'ANY.pdf'))
    })
    expect(result.current.uploading).toBe(true)

    await waitFor(() => expect(result.current.uploading).toBe(false))
    expect(onSuccess).toHaveBeenCalled()
    expect(result.current.error).toBeNull()
  })

  it('surfaces a failed upload as a user-facing error instead of throwing', async () => {
    vi.spyOn(dataService, 'uploadPDF').mockRejectedValue(new Error('ANY_UPLOAD_FAILURE'))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useUploadDocument(onSuccess))

    await act(async () => {
      await result.current.upload(new File(['x'], 'ANY.pdf'))
    })

    expect(result.current.error).toBe('ANY_UPLOAD_FAILURE')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})

describe('useDeleteDocument', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('surfaces a failed delete as a user-facing error', async () => {
    vi.spyOn(dataService, 'deleteDocument').mockRejectedValue(new Error('ANY_DELETE_FAILURE'))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useDeleteDocument(onSuccess))

    await act(async () => {
      await result.current.remove(1)
    })

    expect(result.current.error).toBe('ANY_DELETE_FAILURE')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})

describe('useImportExternalFiling', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('calls onSuccess and clears importingId/error on a successful import', async () => {
    vi.spyOn(dataService, 'importExternalFiling').mockResolvedValue({
      id: 2,
      filename: 'Senus PLC Information Document.pdf',
      file_size: 1_056_649,
      status: 'completed',
      created_at: '2026-07-08T00:00:00Z',
      extraction_confidence_tier: null,
      superseded_by_document_id: null,
    })
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useImportExternalFiling(onSuccess))

    act(() => {
      result.current.importFiling('info-doc-id')
    })
    expect(result.current.importingId).toBe('info-doc-id')

    await waitFor(() => expect(result.current.importingId).toBeNull())
    expect(onSuccess).toHaveBeenCalled()
    expect(result.current.error).toBeNull()
  })

  it('surfaces a failed import as a user-facing error instead of throwing', async () => {
    vi.spyOn(dataService, 'importExternalFiling').mockRejectedValue(new Error('ANY_IMPORT_FAILURE'))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useImportExternalFiling(onSuccess))

    await act(async () => {
      await result.current.importFiling('info-doc-id')
    })

    expect(result.current.error).toBe('ANY_IMPORT_FAILURE')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})

describe('useApproveDocument', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('calls onSuccess and clears approvingId/error on a successful approve', async () => {
    vi.spyOn(dataService, 'approveDocument').mockResolvedValue({
      id: 3,
      filename: 'ADF Farm Solutions Consolidated Financial Statements.pdf',
      file_size: 6_800_000,
      status: 'completed',
      created_at: '2026-07-08T00:00:00Z',
      extraction_confidence_tier: 'auto_accept',
      superseded_by_document_id: null,
      financial_metrics: {
        revenue: null,
        customers: null,
        cash: 120_000,
        ebitda: null,
        gross_margin: null,
        operating_margin: null,
        extraction_confidence: 55,
        extraction_confidence_tier: 'auto_accept',
        extraction_confidence_reasons: null,
      },
    })
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useApproveDocument(onSuccess))

    act(() => {
      result.current.approve(3)
    })
    expect(result.current.approvingId).toBe(3)

    await waitFor(() => expect(result.current.approvingId).toBeNull())
    expect(onSuccess).toHaveBeenCalled()
    expect(result.current.error).toBeNull()
  })

  it('surfaces a failed approve as a user-facing error instead of throwing', async () => {
    vi.spyOn(dataService, 'approveDocument').mockRejectedValue(new Error('ANY_APPROVE_FAILURE'))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useApproveDocument(onSuccess))

    await act(async () => {
      await result.current.approve(3)
    })

    expect(result.current.error).toBe('ANY_APPROVE_FAILURE')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})

describe('useRegenerateReport', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('surfaces a failed regenerate as a user-facing error', async () => {
    vi.spyOn(dataService, 'regenerateReport').mockRejectedValue(new Error('ANY_REGEN_FAILURE'))
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useRegenerateReport(onSuccess))

    await act(async () => {
      await result.current.regenerate(1)
    })

    expect(result.current.error).toBe('ANY_REGEN_FAILURE')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})
