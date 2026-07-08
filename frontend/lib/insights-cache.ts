import type { Metrics } from './data-service'
import type { Insight } from './insights'

// Persisted to localStorage (not just module scope) so a hard page reload
// doesn't lose the cache -- previously, refreshing the browser wiped this
// module's state entirely, forcing a fresh Gemini call for the exact same
// data every time, needlessly burning quota on a genuinely single-user tool
// where the underlying report data changes at most a few times a year.
// Module-level variables still back every read/write (no localStorage round
// trip per render) -- localStorage is only consulted once, at module load,
// to seed them.
const STORAGE_KEY = 'senus-ai-insights-cache-v1'

interface StoredCache {
  metricsKey: string
  insights: Insight[]
}

function loadFromStorage(): StoredCache | null {
  // This module is imported by a 'use client' component, but Next.js still
  // evaluates client-component modules during server rendering -- guard
  // against running in that (and any other non-browser, e.g. test) context.
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as StoredCache) : null
  } catch {
    // Malformed JSON from a prior schema, or localStorage unavailable
    // (private browsing, quota exceeded) -- caching is a pure optimization,
    // never worth crashing the dashboard over.
    return null
  }
}

function saveToStorage(entry: StoredCache | null): void {
  if (typeof window === 'undefined') return
  try {
    if (entry) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entry))
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // Same reasoning as loadFromStorage -- never let a storage failure
    // surface as a dashboard error.
  }
}

const initial = loadFromStorage()

// Module-level (not React state) cache, so it survives a component remount
// within the same browser session -- e.g. navigating to Settings to change
// the theme and back to "/" unmounts AiInsights, which would otherwise reset
// a per-instance guard and trigger a wasted, non-deterministic Gemini
// re-call for data that hasn't actually changed. Keyed by content
// (JSON.stringify), not object reference, since a remount always produces a
// structurally-identical-but-distinct `metrics` object from a fresh fetch.
let cachedInsights: Insight[] | null = initial?.insights ?? null
let cachedMetricsKey: string | null = initial?.metricsKey ?? null

export function getCachedInsights(metrics: Metrics): Insight[] | null {
  return cachedMetricsKey === JSON.stringify(metrics) ? cachedInsights : null
}

export function setCachedInsights(metrics: Metrics, insights: Insight[]): void {
  const metricsKey = JSON.stringify(metrics)
  cachedMetricsKey = metricsKey
  cachedInsights = insights
  saveToStorage({ metricsKey, insights })
}

export function hasCachedInsightsFor(metrics: Metrics): boolean {
  return cachedMetricsKey === JSON.stringify(metrics)
}

// Test-only: this module is a singleton shared across every test in a file
// (vitest doesn't reset modules between `it()` blocks by default), so tests
// need a way to start from a clean cache.
export function resetInsightsCache(): void {
  cachedInsights = null
  cachedMetricsKey = null
  saveToStorage(null)
}
