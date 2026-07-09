import { describe, it, expect } from 'vitest'
import {
  projectSeries,
  projectFromGuidance,
  summarizeGuidanceForecast,
  latestRevenueBaseline,
  SENUS_GROWTH_GUIDANCE,
} from '@/lib/forecast'
import type { ChartDataPoint } from '@/lib/data-service'

// Real callers always pass full ChartDataPoint rows -- document_id/cadence_months
// are irrelevant to projectSeries' own math, so every fixture below just carries
// a stable null/null pair to satisfy the type.
function point(overrides: Partial<ChartDataPoint> & { period: string }): ChartDataPoint {
  return { revenue: null, ebitda: null, cash: null, document_id: null, cadence_months: null, ...overrides }
}

describe('projectSeries', () => {
  it('returns nothing for fewer than 2 known points', () => {
    expect(projectSeries([])).toEqual([])
    expect(projectSeries([point({ period: 'Jan', revenue: 100 })])).toEqual([])
    expect(
      projectSeries([
        point({ period: 'Jan', revenue: null }),
        point({ period: 'Feb', revenue: 100 }),
      ])
    ).toEqual([])
  })

  it('projects a straight line forward for a perfectly linear series', () => {
    const history = [
      point({ period: 'Jan', revenue: 100 }),
      point({ period: 'Feb', revenue: 200 }),
      point({ period: 'Mar', revenue: 300 }),
    ]
    const result = projectSeries(history, 'revenue', 2)

    expect(result).toHaveLength(2)
    expect(result[0].revenue).toBe(400)
    expect(result[1].revenue).toBe(500)
  })

  it('skips null points rather than treating them as 0', () => {
    // Same underlying trend as above with a gap in the middle -- the fit
    // should still follow 100 -> 300, not get dragged toward a fake 0.
    const history = [
      point({ period: 'Jan', revenue: 100 }),
      point({ period: 'Feb', revenue: null }),
      point({ period: 'Mar', revenue: 300 }),
    ]
    const result = projectSeries(history, 'revenue', 1)

    expect(result[0].revenue).toBeGreaterThan(300)
  })

  it('never projects a negative revenue', () => {
    const history = [
      point({ period: 'Jan', revenue: 100 }),
      point({ period: 'Feb', revenue: 50 }),
      point({ period: 'Mar', revenue: 0 }),
    ]
    const result = projectSeries(history, 'revenue', 3)

    for (const pt of result) {
      expect(pt.revenue).toBeGreaterThanOrEqual(0)
    }
  })

  it('projects EBITDA and allows it to stay negative', () => {
    // Real filing values: EBITDA loss deepening from -395,561 to -473,739 --
    // a worsening trend should project further negative, not get floored at 0.
    const history = [
      point({ period: 'Dec 2024', revenue: 340_931, ebitda: -395_561, cash: 72_382 }),
      point({ period: 'Dec 2025', revenue: 354_813, ebitda: -473_739, cash: 735_189 }),
    ]
    const result = projectSeries(history, 'ebitda', 1)

    expect(result[0].ebitda).toBeLessThan(-473_739)
    expect(result[0].revenue).toBeNull()
  })

  it('projects Cash', () => {
    const history = [
      point({ period: 'Dec 2024', revenue: 340_931, ebitda: -395_561, cash: 72_382 }),
      point({ period: 'Dec 2025', revenue: 354_813, ebitda: -473_739, cash: 735_189 }),
    ]
    const result = projectSeries(history, 'cash', 1)

    expect(result[0].cash).toBeGreaterThan(735_189)
  })
})

describe('projectFromGuidance', () => {
  it('compounds forward at the given CAGR, one point per year, future only', () => {
    const points = projectFromGuidance(100_000, 2025, 2028, 0.5)

    expect(points).toEqual([
      { period: 'FY2026', revenue: 150_000 },
      { period: 'FY2027', revenue: 225_000 },
      { period: 'FY2028', revenue: 337_500 },
    ])
  })

  it('defaults to the Senus 2030 guidance when no rate/target year is given', () => {
    const points = projectFromGuidance(837_000, 2025)

    expect(points).toHaveLength(SENUS_GROWTH_GUIDANCE.targetYear - 2025)
    expect(points[points.length - 1].period).toBe('FY2030')
  })

  it('returns nothing for a non-positive base revenue', () => {
    expect(projectFromGuidance(0, 2025)).toEqual([])
    expect(projectFromGuidance(-100, 2025)).toEqual([])
  })

  it('returns nothing when the target year is not after the base year', () => {
    expect(projectFromGuidance(100_000, 2030, 2030)).toEqual([])
    expect(projectFromGuidance(100_000, 2031, 2030)).toEqual([])
  })
})

describe('summarizeGuidanceForecast', () => {
  it('computes the forecast-card figures from a real baseline', () => {
    const summary = summarizeGuidanceForecast(837_000, 2025, 2030, 0.5)

    expect(summary).not.toBeNull()
    expect(summary?.targetYear).toBe(2030)
    expect(summary?.cagrPercent).toBe(50)
    expect(summary?.projectedTarget).toBe(Math.round(837_000 * 1.5 ** 5))
    expect(summary?.growthMultiple).toBeCloseTo(1.5 ** 5, 2)
    expect(summary?.progressToTargetPercent).toBeCloseTo(100 / 1.5 ** 5, 2)
  })

  it('returns null with nothing to project from', () => {
    expect(summarizeGuidanceForecast(0, 2025)).toBeNull()
  })
})

describe('latestRevenueBaseline', () => {
  function point(overrides: Partial<ChartDataPoint> & { period: string }): ChartDataPoint {
    return { revenue: null, ebitda: null, cash: null, document_id: null, cadence_months: null, ...overrides }
  }

  it('finds the most recent point with a real revenue figure and a parseable year', () => {
    const history = [
      point({ period: 'FY2024', revenue: 688_317 }),
      point({ period: 'HY2026', revenue: null }), // no revenue reported
      point({ period: 'FY2025', revenue: 836_991 }),
    ]
    expect(latestRevenueBaseline(history)).toEqual({ revenue: 836_991, year: 2025 })
  })

  it('skips a trailing point with a real revenue but no parseable year', () => {
    const history = [
      point({ period: 'FY2024', revenue: 688_317 }),
      point({ period: 'Next Report 1', revenue: 900_000 }), // a forecast row, no real year
    ]
    expect(latestRevenueBaseline(history)).toEqual({ revenue: 688_317, year: 2024 })
  })

  it('returns null with no usable point at all', () => {
    expect(latestRevenueBaseline([])).toBeNull()
    expect(latestRevenueBaseline([point({ period: 'Unknown', revenue: null })])).toBeNull()
  })
})
