import { describe, it, expect } from 'vitest'
import { calculateChange, getTrend, changeFromHistory } from '@/lib/metrics'

describe('calculateChange', () => {
  it('computes a positive percentage change', () => {
    expect(calculateChange(110, 100)).toBe(10)
  })

  it('computes a negative percentage change', () => {
    expect(calculateChange(90, 100)).toBe(-10)
  })

  it('returns 0 when previous is 0 (avoids divide-by-zero)', () => {
    expect(calculateChange(100, 0)).toBe(0)
  })

  it('treats missing values as 0', () => {
    expect(calculateChange(null, 100)).toBe(-100)
    expect(calculateChange(undefined, undefined)).toBe(0)
  })
})

describe('getTrend', () => {
  it('maps positive/negative/zero change to up/down/neutral', () => {
    expect(getTrend(5)).toBe('up')
    expect(getTrend(-5)).toBe('down')
    expect(getTrend(0)).toBe('neutral')
  })
})

describe('changeFromHistory', () => {
  it('returns neutral/0 for fewer than 2 real points', () => {
    expect(changeFromHistory([])).toEqual({ change: 0, trend: 'neutral' })
    expect(changeFromHistory([10])).toEqual({ change: 0, trend: 'neutral' })
    expect(changeFromHistory([null, 10])).toEqual({ change: 0, trend: 'neutral' })
  })

  it('compares the last two non-null points', () => {
    expect(changeFromHistory([100, 110])).toEqual({ change: 10, trend: 'up' })
  })

  it('skips a null tail rather than treating it as 0', () => {
    // Last real points are 100 -> 110 (10% up), not 110 -> null.
    expect(changeFromHistory([100, 110, null])).toEqual({ change: 10, trend: 'up' })
  })
})
