/**
 * Builds real, honest KPI subtitle text from the actual AI-extracted
 * reporting period (e.g. "H1 2025" vs "H1 2024"), instead of a fabricated
 * cadence claim ("vs last quarter"/"vs last month") that may not match what
 * the filing actually reports. Every KPI backed by a real prior-period
 * comparative shares the same current/prior period, since this codebase's
 * metrics all come from the same single filing.
 */
export function periodComparisonLabel(
  currentPeriod: string | null,
  priorPeriod: string | null,
  fallback: string
): string {
  if (currentPeriod && priorPeriod) return `${priorPeriod} vs ${currentPeriod}`
  if (priorPeriod) return `vs ${priorPeriod}`
  return fallback
}

/**
 * For metrics with no real prior-period comparative (e.g. `customers`,
 * `bookings`) -- states the current period as context without implying a
 * comparison that doesn't exist.
 */
export function periodContextLabel(currentPeriod: string | null, fallback: string): string {
  return currentPeriod ? `as of ${currentPeriod}` : fallback
}
