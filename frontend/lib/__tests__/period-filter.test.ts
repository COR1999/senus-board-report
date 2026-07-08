import { describe, it, expect } from 'vitest'
import { buildPeriodOptions, matchesPeriod } from '@/lib/period-filter'

describe('buildPeriodOptions', () => {
  it('derives distinct year-month options from the given dates, newest first', () => {
    const options = buildPeriodOptions([
      '2026-07-06T12:00:00Z',
      '2026-06-15T12:00:00Z',
      '2026-07-08T09:00:00Z', // same month as the first -- should not duplicate
    ])

    expect(options).toEqual([
      { value: '2026-07', label: 'July 2026' },
      { value: '2026-06', label: 'June 2026' },
    ])
  })

  it('ignores invalid dates instead of crashing', () => {
    // Noon UTC (not midnight) so this doesn't roll into the prior/next
    // calendar day -- and therefore month -- under `getMonth()`'s local-
    // time semantics on machines west of UTC.
    expect(buildPeriodOptions(['not-a-date', '2026-01-15T12:00:00Z'])).toEqual([
      { value: '2026-01', label: 'January 2026' },
    ])
  })

  it('returns an empty list for no dates', () => {
    expect(buildPeriodOptions([])).toEqual([])
  })
})

describe('matchesPeriod', () => {
  it('matches a date within the given year-month', () => {
    expect(matchesPeriod('2026-07-06T12:00:00Z', '2026-07')).toBe(true)
  })

  it('does not match a date outside the given year-month', () => {
    // Noon UTC, not end-of-day -- avoids rolling into July under
    // `getMonth()`'s local-time semantics on machines east of UTC.
    expect(matchesPeriod('2026-06-30T12:00:00Z', '2026-07')).toBe(false)
  })
})
