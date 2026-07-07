/**
 * For metrics with no real prior-period comparative (e.g. `customers`,
 * `bookings`) -- states the current period as context without implying a
 * comparison that doesn't exist.
 */
export function periodContextLabel(currentPeriod: string | null, fallback: string): string {
  return currentPeriod ? `as of ${currentPeriod}` : fallback
}
