import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
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

  describe('enabled', () => {
    it('skips fetching entirely and never enters a loading state when false', async () => {
      const fetcher = vi.fn().mockResolvedValue('ANY_VALUE')
      const { result } = renderHook(() => useAsyncData(fetcher, { enabled: false }))

      expect(result.current.loading).toBe(false)
      expect(result.current.data).toBeNull()
      expect(fetcher).not.toHaveBeenCalled()
    })

    it('starts fetching once enabled flips from false to true', async () => {
      const fetcher = vi.fn().mockResolvedValue('ANY_VALUE')
      const { result, rerender } = renderHook(({ enabled }) => useAsyncData(fetcher, { enabled }), {
        initialProps: { enabled: false },
      })
      expect(fetcher).not.toHaveBeenCalled()

      rerender({ enabled: true })

      await waitFor(() => expect(result.current.data).toBe('ANY_VALUE'))
      expect(fetcher).toHaveBeenCalledTimes(1)
    })
  })

  describe('pollIntervalMs', () => {
    afterEach(() => {
      vi.useRealTimers()
    })

    it('re-invokes the fetcher in the background on the given interval', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const fetcher = vi.fn().mockResolvedValue({ value: 1 })
      renderHook(() => useAsyncData(fetcher, { pollIntervalMs: 1000 }))

      await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))

      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      expect(fetcher).toHaveBeenCalledTimes(2)

      await act(async () => {
        vi.advanceTimersByTime(2000)
      })
      expect(fetcher).toHaveBeenCalledTimes(4)
    })

    it('keeps the same data reference when a poll returns unchanged content', async () => {
      // Critical for consumers like AiInsights that key a useEffect on this
      // object -- a background poll returning identical content must never
      // hand back a *new* object, or it would look like real new data and
      // re-trigger an unnecessary OpenAI call every poll tick.
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const fetcher = vi.fn().mockResolvedValue({ revenue: 100 })
      const { result } = renderHook(() => useAsyncData(fetcher, { pollIntervalMs: 1000 }))

      await vi.waitFor(() => expect(result.current.data).toEqual({ revenue: 100 }))
      const firstReference = result.current.data

      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))

      expect(result.current.data).toBe(firstReference)
    })

    it('replaces the data reference when a poll returns genuinely new content', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const fetcher = vi.fn()
        .mockResolvedValueOnce({ revenue: 100 })
        .mockResolvedValueOnce({ revenue: 200 })
      const { result } = renderHook(() => useAsyncData(fetcher, { pollIntervalMs: 1000 }))

      await vi.waitFor(() => expect(result.current.data).toEqual({ revenue: 100 }))

      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      await vi.waitFor(() => expect(result.current.data).toEqual({ revenue: 200 }))
    })

    it('does not flip loading back to true on a background poll', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const fetcher = vi.fn().mockResolvedValue({ revenue: 100 })
      const { result } = renderHook(() => useAsyncData(fetcher, { pollIntervalMs: 1000 }))

      await vi.waitFor(() => expect(result.current.loading).toBe(false))

      await act(async () => {
        vi.advanceTimersByTime(1000)
      })
      await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))

      expect(result.current.loading).toBe(false)
    })
  })
})
