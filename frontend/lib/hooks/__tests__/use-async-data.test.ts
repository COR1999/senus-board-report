import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useAsyncData } from '@/lib/hooks/use-async-data'

describe('useAsyncData', () => {
  it('starts loading with null data, then resolves', async () => {
    const fetcher = vi.fn().mockResolvedValue('ANY_VALUE')
    const { result } = renderHook(() => useAsyncData(fetcher))

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBe('ANY_VALUE')
    expect(result.current.error).toBeNull()
  })

  it('surfaces a rejected fetcher as a string error, not a thrown exception', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('ANY_FAILURE'))
    const { result } = renderHook(() => useAsyncData(fetcher))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('ANY_FAILURE')
    expect(result.current.data).toBeNull()
  })

  it('refetch() re-invokes the fetcher and clears a prior error on success', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('ANY_FAILURE')).mockResolvedValueOnce('RECOVERED')
    const { result } = renderHook(() => useAsyncData(fetcher))

    await waitFor(() => expect(result.current.error).toBe('ANY_FAILURE'))

    act(() => result.current.refetch())

    await waitFor(() => expect(result.current.data).toBe('RECOVERED'))
    expect(result.current.error).toBeNull()
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
