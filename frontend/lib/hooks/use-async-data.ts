'use client'

import { useCallback, useEffect, useState } from 'react'

export interface AsyncDataState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export interface UseAsyncDataOptions {
  deps?: unknown[]
  /**
   * When set, re-fetches in the background on this interval -- so the UI
   * picks up a change (e.g. a newly generated report) without the user
   * needing to reload the page or navigate away and back. Background polls
   * never flip `loading` back to true (no repeating skeleton flash), and
   * only replace `data` if the fetched value actually differs by content
   * (not just a new object reference) -- both to avoid the flash and to
   * avoid re-triggering downstream effects keyed on this value (e.g.
   * AiInsights' OpenAI call) on every no-op poll.
   */
  pollIntervalMs?: number
}

/**
 * Generic data-fetching hook: loading/error/data/refetch, so individual
 * components stop hand-rolling the same useState+useEffect boilerplate.
 * `data` starts `null` (not a fabricated empty shape) so callers can tell
 * "still loading" apart from "loaded, genuinely empty".
 *
 * Most `data-service.ts` GET functions already catch their own network
 * errors and resolve with mock/fallback data rather than rejecting (see
 * `getMetrics`, `getReports`, etc.) -- for those, `error` here will rarely
 * fire, which matches today's "always show something, warn to console"
 * behavior. It exists for fetchers that do reject (mutations, or any future
 * endpoint without a fallback) so those get a real, user-facing error state
 * instead of being silently swallowed.
 */
export function useAsyncData<T>(fetcher: () => Promise<T>, options: UseAsyncDataOptions = {}): AsyncDataState<T> {
  const { deps = [], pollIntervalMs } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // Reset loading/error here, in a plain callback -- not synchronously inside
  // the effect below, which react-hooks' set-state-in-effect rule flags as a
  // cascading-render risk. The initial mount is already `loading: true` via
  // useState's initial value, so this reset only needs to run on refetch.
  const refetch = useCallback(() => {
    setLoading(true)
    setError(null)
    setNonce((n) => n + 1)
  }, [])

  useEffect(() => {
    let cancelled = false

    const load = () => {
      fetcher()
        .then((result) => {
          if (cancelled) return
          // Compare by content, not reference -- a background poll that
          // returns identical data must not hand the caller a new object
          // (that would look like a "change" to anything keyed on this
          // value, e.g. AiInsights' `useEffect([metrics])`).
          setData((prev) => (prev !== null && JSON.stringify(prev) === JSON.stringify(result) ? prev : result))
          setError(null)
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load data')
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }

    load()

    const timer = pollIntervalMs ? setInterval(load, pollIntervalMs) : undefined

    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, pollIntervalMs, ...deps])

  return { data, loading, error, refetch }
}
