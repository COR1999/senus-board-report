import { describe, it, expect } from 'vitest'
import { projectSeries } from '@/lib/forecast'

describe('projectSeries', () => {
  it('returns nothing for fewer than 2 known points', () => {
    expect(projectSeries([])).toEqual([])
    expect(projectSeries([{ period: 'Jan', revenue: 100, ebitda: null, cash: null }])).toEqual([])
    expect(
      projectSeries([
        { period: 'Jan', revenue: null, ebitda: null, cash: null },
        { period: 'Feb', revenue: 100, ebitda: null, cash: null },
      ])
    ).toEqual([])
  })

  it('projects a straight line forward for a perfectly linear series', () => {
    const history = [
      { period: 'Jan', revenue: 100, ebitda: null, cash: null },
      { period: 'Feb', revenue: 200, ebitda: null, cash: null },
      { period: 'Mar', revenue: 300, ebitda: null, cash: null },
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
      { period: 'Jan', revenue: 100, ebitda: null, cash: null },
      { period: 'Feb', revenue: null, ebitda: null, cash: null },
      { period: 'Mar', revenue: 300, ebitda: null, cash: null },
    ]
    const result = projectSeries(history, 'revenue', 1)

    expect(result[0].revenue).toBeGreaterThan(300)
  })

  it('never projects a negative revenue', () => {
    const history = [
      { period: 'Jan', revenue: 100, ebitda: null, cash: null },
      { period: 'Feb', revenue: 50, ebitda: null, cash: null },
      { period: 'Mar', revenue: 0, ebitda: null, cash: null },
    ]
    const result = projectSeries(history, 'revenue', 3)

    for (const point of result) {
      expect(point.revenue).toBeGreaterThanOrEqual(0)
    }
  })

  it('projects EBITDA and allows it to stay negative', () => {
    // Real filing values: EBITDA loss deepening from -395,561 to -473,739 --
    // a worsening trend should project further negative, not get floored at 0.
    const history = [
      { period: 'Dec 2024', revenue: 340_931, ebitda: -395_561, cash: 72_382 },
      { period: 'Dec 2025', revenue: 354_813, ebitda: -473_739, cash: 735_189 },
    ]
    const result = projectSeries(history, 'ebitda', 1)

    expect(result[0].ebitda).toBeLessThan(-473_739)
    expect(result[0].revenue).toBeNull()
  })

  it('projects Cash', () => {
    const history = [
      { period: 'Dec 2024', revenue: 340_931, ebitda: -395_561, cash: 72_382 },
      { period: 'Dec 2025', revenue: 354_813, ebitda: -473_739, cash: 735_189 },
    ]
    const result = projectSeries(history, 'cash', 1)

    expect(result[0].cash).toBeGreaterThan(735_189)
  })
})
