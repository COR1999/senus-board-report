import { describe, it, expect } from 'vitest'
import { formatPercent, getTrendStyle, getTrendColor } from '@/lib/format'

describe('formatPercent', () => {
  it('formats a plain percentage', () => {
    expect(formatPercent(4.1)).toBe('4.1%')
  })

  it('adds a + sign for positive values when showSign is set', () => {
    expect(formatPercent(4.1, { showSign: true })).toBe('+4.1%')
  })

  it('does not add a sign for negative or zero values even with showSign', () => {
    expect(formatPercent(-4.1, { showSign: true })).toBe('-4.1%')
    expect(formatPercent(0, { showSign: true })).toBe('0%')
  })
})

describe('getTrendStyle', () => {
  it('gives neutral its own distinct styling, not up/down reused', () => {
    const up = getTrendStyle('up')
    const down = getTrendStyle('down')
    const neutral = getTrendStyle('neutral')

    expect(neutral.textClass).not.toBe(up.textClass)
    expect(neutral.textClass).not.toBe(down.textClass)
    expect(neutral.Icon).not.toBe(up.Icon)
    expect(neutral.Icon).not.toBe(down.Icon)
  })
})

describe('getTrendColor', () => {
  it('returns distinct hex colors per trend', () => {
    expect(getTrendColor('up')).toBe('#10b981')
    expect(getTrendColor('down')).toBe('#f43f5e')
    expect(getTrendColor('neutral')).toBe('#64748b')
  })
})
