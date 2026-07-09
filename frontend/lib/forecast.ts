import type { ChartDataPoint } from '@/lib/data-service'

export type ForecastMetric = 'revenue' | 'ebitda' | 'cash'

// ==================== Method Two: management guidance ====================
//
// Method One (projectSeries below) needs 3+ real points in a cadence to fit
// a trend through -- see revenue-chart.tsx's determineRenderMode. With only
// two real reporting periods on file today, that bar isn't cleared for
// either the Full-Year or Half-Year series. Rather than show no forecast at
// all, Method Two projects forward from the latest real revenue figure
// using Senus's own publicly stated growth target instead of an invented
// trend -- "forecast the future from real guidance," never "fabricate the
// past" (see docs/dashboard-review.md's "Forecast, redesigned" section).

/**
 * Senus's own stated growth guidance. VERIFY before relying on this in a
 * real board presentation: the exact wording, base year, and target year
 * should be confirmed against the Information Document's own text (the
 * same sourcing discipline financial_metrics_extractor.py applies to every
 * regex it trusts) -- this constant is a best-effort citation from the
 * assignment brief, not independently re-derived from the source PDF text
 * in this branch.
 */
export const SENUS_GROWTH_GUIDANCE = {
  cagr: 0.5,
  targetYear: 2030,
  label: 'Senus 2030 strategy (minimum 50% CAGR)',
} as const

export interface GuidanceForecastPoint {
  period: string
  revenue: number
}

/**
 * Projects revenue forward from `baseRevenue`/`baseYear` at a compound
 * annual growth rate to `targetYear` -- one point per year, current year
 * excluded (the first point is `baseYear + 1`). Forecasts ONLY the future:
 * unlike Method One, this never touches historical data at all, so there's
 * no risk of it implying a fabricated past trend. Returns an empty array
 * when there's nothing to project (`baseRevenue` non-positive, or
 * `targetYear` not after `baseYear`).
 */
export function projectFromGuidance(
  baseRevenue: number,
  baseYear: number,
  targetYear: number = SENUS_GROWTH_GUIDANCE.targetYear,
  cagr: number = SENUS_GROWTH_GUIDANCE.cagr
): GuidanceForecastPoint[] {
  const years = targetYear - baseYear
  if (baseRevenue <= 0 || years <= 0) return []
  return Array.from({ length: years }, (_, i) => {
    const yearsOut = i + 1
    return {
      period: `FY${baseYear + yearsOut}`,
      revenue: Math.round(baseRevenue * Math.pow(1 + cagr, yearsOut)),
    }
  })
}

export interface GuidanceForecastSummary {
  /** Projected revenue in the target year (e.g. 2030). */
  projectedTarget: number
  targetYear: number
  /** As a percentage, e.g. 50 for 50%. */
  cagrPercent: number
  /** Projected-target ÷ current revenue, e.g. 7.6 for a 7.6x multiple. */
  growthMultiple: number
  /** Current revenue as a percentage of the projected target, 0-100. */
  progressToTargetPercent: number
}

/**
 * The "forecast cards" summary (Projected Revenue, CAGR, Growth Multiple,
 * Progress to Target) -- often more informative than another chart, per
 * the same reasoning progress/gauge components are preferred elsewhere on
 * this dashboard for a single data point. `null` when there's no real
 * baseline revenue to project from at all.
 */
export function summarizeGuidanceForecast(
  baseRevenue: number,
  baseYear: number,
  targetYear: number = SENUS_GROWTH_GUIDANCE.targetYear,
  cagr: number = SENUS_GROWTH_GUIDANCE.cagr
): GuidanceForecastSummary | null {
  const points = projectFromGuidance(baseRevenue, baseYear, targetYear, cagr)
  if (points.length === 0) return null
  const projectedTarget = points[points.length - 1].revenue
  return {
    projectedTarget,
    targetYear,
    cagrPercent: cagr * 100,
    growthMultiple: projectedTarget / baseRevenue,
    progressToTargetPercent: (baseRevenue / projectedTarget) * 100,
  }
}

/**
 * The most recent real (non-null) revenue point in the chart's whole
 * history, plus the calendar year parsed out of its own period label --
 * the baseline Method Two projects forward from. `null` when no chart
 * point has both a real revenue figure and a parseable 4-digit year.
 */
export function latestRevenueBaseline(history: ChartDataPoint[]): { revenue: number; year: number } | null {
  for (let i = history.length - 1; i >= 0; i--) {
    const point = history[i]
    if (point.revenue == null) continue
    const match = point.period.match(/(\d{4})/)
    if (!match) continue
    return { revenue: point.revenue, year: Number(match[1]) }
  }
  return null
}

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
      // No real document backs a projected point -- see RevenueChart's own
      // reasoning for why its synthetic prior-period point does the same.
      document_id: null,
      cadence_months: null,
      [metric]: value,
    }
  })
}
