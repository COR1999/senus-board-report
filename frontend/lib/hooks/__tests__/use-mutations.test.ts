import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import * as dataService from '@/lib/data-service'
import { useUploadDocument, useDeleteDocument, useRegenerateReport } from '@/lib/hooks/use-mutations'

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
