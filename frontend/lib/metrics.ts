import type { Trend } from '@/lib/format'

/**
 * General-purpose delta utilities mirroring the backend's
 * MetricsService.calculate_change / get_trend (backend/app/services/metrics_service.py).
 * NOT used to override the API's authoritative `change`/`trend` fields on a
 * KPI -- these exist for any future client-side delta needs (e.g. deriving
 * a change from a sparkline's `history` series), with their own tests.
 */

/**
 * Percentage change between two values, e.g. calculateChange(110, 100) -> 10.
 * Missing (null/undefined) values are treated as 0, matching the backend's
 * `current or 0` / `previous or 0` behavior. Returns 0 if previous is 0
 * (avoids a divide-by-zero rather than throwing).
 */
export function calculateChange(
  current: number | null | undefined,
  previous: number | null | undefined
): number {
  const curr = current ?? 0
  const prev = previous ?? 0
  if (prev === 0) return 0
  return ((curr - prev) / prev) * 100
}

/** Trend direction implied by a percentage change: positive -> up, negative -> down, 0 -> neutral. */
export function getTrend(change: number): Trend {
  if (change > 0) return 'up'
  if (change < 0) return 'down'
  return 'neutral'
}

/**
 * Derives a { change, trend } pair from a history series (oldest -> newest)
 * by comparing the last two *non-null* points. Null entries (fields a
 * document didn't report) are skipped rather than treated as 0, so a single
 * missing data point doesn't read as a fake drop to zero.
 * Returns `{ change: 0, trend: 'neutral' }` if fewer than 2 real points exist.
 */
export function changeFromHistory(history: (number | null)[]): { change: number; trend: Trend } {
  const points = history.filter((v): v is number => v !== null)
  if (points.length < 2) return { change: 0, trend: 'neutral' }
  const change = calculateChange(points[points.length - 1], points[points.length - 2])
  const rounded = Math.round(change * 10) / 10
  return { change: rounded, trend: getTrend(rounded) }
}
