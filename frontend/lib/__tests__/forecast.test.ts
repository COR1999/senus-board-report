import { describe, it, expect } from 'vitest'
import { projectRevenue } from '@/lib/forecast'

describe('projectRevenue', () => {
  it('returns nothing for fewer than 2 known points', () => {
    expect(projectRevenue([])).toEqual([])
    expect(projectRevenue([{ period: 'Jan', revenue: 100 }])).toEqual([])
    expect(
      projectRevenue([
        { period: 'Jan', revenue: null },
        { period: 'Feb', revenue: 100 },
      ])
    ).toEqual([])
  })

  it('projects a straight line forward for a perfectly linear series', () => {
    const history = [
      { period: 'Jan', revenue: 100 },
      { period: 'Feb', revenue: 200 },
      { period: 'Mar', revenue: 300 },
    ]
    const result = projectRevenue(history, 2)

    expect(result).toHaveLength(2)
    expect(result[0].revenue).toBe(400)
    expect(result[1].revenue).toBe(500)
  })

  it('skips null points rather than treating them as 0', () => {
    // Same underlying trend as above with a gap in the middle -- the fit
    // should still follow 100 -> 300, not get dragged toward a fake 0.
    const history = [
      { period: 'Jan', revenue: 100 },
      { period: 'Feb', revenue: null },
      { period: 'Mar', revenue: 300 },
    ]
    const result = projectRevenue(history, 1)

    expect(result[0].revenue).toBeGreaterThan(300)
  })

  it('never projects a negative revenue', () => {
    const history = [
      { period: 'Jan', revenue: 100 },
      { period: 'Feb', revenue: 50 },
      { period: 'Mar', revenue: 0 },
    ]
    const result = projectRevenue(history, 3)

    for (const point of result) {
      expect(point.revenue).toBeGreaterThanOrEqual(0)
    }
  })
})
