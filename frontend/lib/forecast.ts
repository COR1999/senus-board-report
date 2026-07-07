import type { ChartDataPoint } from '@/lib/data-service'

export type ForecastMetric = 'revenue' | 'ebitda' | 'cash'

/**
 * Projects future points for the given metric using ordinary least-squares
 * linear regression over the known (non-null) points of that metric. This is
 * a simple visual projection for the dashboard's forecast toggle -- not a
 * financial model. Returns an empty array if there are fewer than 2 known
 * points to fit a line through.
 *
 * @param metric which series to project ('revenue', 'ebitda', or 'cash')
 * @param periodsAhead how many future points to project (default 3)
 */
export function projectSeries(
  history: ChartDataPoint[],
  metric: ForecastMetric = 'revenue',
  periodsAhead: number = 3
): ChartDataPoint[] {
  const known = history
    .map((point, index) => ({ index, value: point[metric] }))
    .filter((p): p is { index: number; value: number } => p.value !== null)

  if (known.length < 2) return []

  const n = known.length
  const sumX = known.reduce((acc, p) => acc + p.index, 0)
  const sumY = known.reduce((acc, p) => acc + p.value, 0)
  const sumXY = known.reduce((acc, p) => acc + p.index * p.value, 0)
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
    const projected = Math.round(slope * index + intercept)
    // Revenue can never legitimately go negative -- EBITDA/Cash can (EBITDA
    // is currently negative for this filing), so only floor at 0 for revenue.
    const value = metric === 'revenue' ? Math.max(0, projected) : projected
    return {
      // "+1"/"+2"/"+3" read like leftover debug notation. Real periods can
      // be irregular, AI-extracted strings ("HY2026", "Q3 2025", ...) with
      // no reliable way to compute a real future calendar date -- "Next
      // Report N" is honest about tracking Senus's report cadence (per
      // this function's own docstring, a simple trendline projection, not
      // a real future calendar period) without implying a precise date.
      period: `Next Report ${i + 1}`,
      revenue: null,
      ebitda: null,
      cash: null,
      [metric]: value,
    }
  })
}
