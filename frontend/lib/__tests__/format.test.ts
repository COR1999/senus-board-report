import { describe, it, expect } from 'vitest'
import { formatPercent, getTrendStyle, getTrendColor, getValueTextClass } from '@/lib/format'

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

describe('getValueTextClass', () => {
  it('uses the trend color directly when a real trend exists, regardless of the value', () => {
    expect(getValueTextClass('down', '€140K')).toBe(getTrendStyle('down').textClass)
    expect(getValueTextClass('up', '-€10K')).toBe(getTrendStyle('up').textClass)
  })

  it('renders a negative value in the "down" color even when trend is neutral', () => {
    // Real production bug: EBITDA at -€613K rendered in plain black text
    // because it had no prior-period comparative (trend "neutral", the "no
    // data" case) -- the value being deeply negative was never considered.
    expect(getValueTextClass('neutral', '-€613K')).toBe(getTrendStyle('down').textClass)
    expect(getValueTextClass('neutral', '-73.3%')).toBe(getTrendStyle('down').textClass)
  })

  it('renders a non-negative neutral value in the plain default color', () => {
    expect(getValueTextClass('neutral', '36')).toBe('text-foreground')
    expect(getValueTextClass('neutral', '€0')).toBe('text-foreground')
  })

  it('treats "N/A" (no leading minus) as non-negative', () => {
    expect(getValueTextClass('neutral', 'N/A')).toBe('text-foreground')
  })
})

describe('getTrendColor', () => {
  it('returns distinct hex colors per trend', () => {
    expect(getTrendColor('up')).toBe('#10b981')
    expect(getTrendColor('down')).toBe('#f43f5e')
    expect(getTrendColor('neutral')).toBe('#64748b')
  })
})
