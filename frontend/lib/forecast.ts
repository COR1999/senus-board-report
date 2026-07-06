import type { ChartDataPoint } from '@/lib/data-service'

/**
 * Projects future revenue points using ordinary least-squares linear
 * regression over the known (non-null) points. This is a simple visual
 * projection for the dashboard's forecast toggle -- not a financial model.
 * Returns an empty array if there are fewer than 2 known points to fit a
 * line through.
 *
 * @param periodsAhead how many future points to project (default 3)
 */
export function projectRevenue(
  history: ChartDataPoint[],
  periodsAhead: number = 3
): ChartDataPoint[] {
  const known = history
    .map((point, index) => ({ index, revenue: point.revenue }))
    .filter((p): p is { index: number; revenue: number } => p.revenue !== null)

  if (known.length < 2) return []

  const n = known.length
  const sumX = known.reduce((acc, p) => acc + p.index, 0)
  const sumY = known.reduce((acc, p) => acc + p.revenue, 0)
  const sumXY = known.reduce((acc, p) => acc + p.index * p.revenue, 0)
  const sumXX = known.reduce((acc, p) => acc + p.index * p.index, 0)

  const denominator = n * sumXX - sumX * sumX
  // All known points share the same index (shouldn't happen with 2+ distinct
  // history entries, but guards the division below).
  if (denominator === 0) return []

  const slope = (n * sumXY - sumX * sumY) / denominator
  const intercept = (sumY - slope * sumX) / n

  const lastIndex = history.length - 1
  return Array.from({ length: periodsAhead }, (_, i) => {
    const index = lastIndex + i + 1
    return {
      // "+1"/"+2"/"+3" read like leftover debug notation. Real periods can
      // be irregular, AI-extracted strings ("HY2026", "Q3 2025", ...) with
      // no reliable way to compute "the next one" -- "Projected N" is
      // honest about these being a simple trendline projection (per this
      // function's own docstring), not a real future calendar period.
      period: `Projected ${i + 1}`,
      revenue: Math.max(0, Math.round(slope * index + intercept)),
    }
  })
}
