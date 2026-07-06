'use client'

import { useCallback, useEffect, useState } from 'react'

export interface AsyncDataState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
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
export function useAsyncData<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncDataState<T> {
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

    fetcher()
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...deps])

  return { data, loading, error, refetch }
}
