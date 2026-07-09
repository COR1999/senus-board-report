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
   * AiInsights' Gemini call) on every no-op poll.
   */
  pollIntervalMs?: number
  /**
   * When `false`, skips fetching entirely (no request, `loading` stays
   * `false`, `data` stays `null`) -- for fetch-on-demand cases like the
   * document review sheet, which shouldn't hit the network for every row
   * on the page, only the one a user actually opens. Defaults to `true`
   * (today's always-fetch-on-mount behavior, unchanged for every existing
   * caller).
   */
  enabled?: boolean
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
  const { deps = [], pollIntervalMs, enabled = true } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // Adjusting state during render -- React's own recommended pattern for
  // "reset some state when a prop changes" (see react.dev, "You Might Not
  // Need an Effect") -- rather than a synchronous setState call inside the
  // effect below, which react-hooks' set-state-in-effect rule flags as a
  // cascading-render risk. `enabled` flipping false needs `loading` reset
  // immediately, including mid-fetch: the in-flight fetch's own `.finally`
  // below is skipped once `cancelled` is set (see the effect's cleanup), so
  // nothing else would ever clear a stuck `loading: true` otherwise.
  const [prevEnabled, setPrevEnabled] = useState(enabled)
  if (enabled !== prevEnabled) {
    setPrevEnabled(enabled)
    if (!enabled) setLoading(false)
  }

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
    if (!enabled) {
      return
    }

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
  }, [nonce, pollIntervalMs, enabled, ...deps])

  return { data, loading, error, refetch }
}
