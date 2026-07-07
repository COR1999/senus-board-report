import type { Metrics } from './data-service'
import type { Insight } from './insights'

// Module-level (not React state) cache, so it survives a component remount
// within the same browser session -- e.g. navigating to Settings to change
// the theme and back to "/" unmounts AiInsights, which would otherwise reset
// a per-instance guard and trigger a wasted, non-deterministic Gemini
// re-call for data that hasn't actually changed. Keyed by content
// (JSON.stringify), not object reference, since a remount always produces a
// structurally-identical-but-distinct `metrics` object from a fresh fetch.
let cachedInsights: Insight[] | null = null
let cachedMetricsKey: string | null = null

export function getCachedInsights(metrics: Metrics): Insight[] | null {
  return cachedMetricsKey === JSON.stringify(metrics) ? cachedInsights : null
}

export function setCachedInsights(metrics: Metrics, insights: Insight[]): void {
  cachedMetricsKey = JSON.stringify(metrics)
  cachedInsights = insights
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
}
