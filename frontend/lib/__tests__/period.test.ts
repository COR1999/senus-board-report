import { describe, it, expect } from 'vitest'
import { periodComparisonLabel, periodContextLabel } from '@/lib/period'

describe('periodComparisonLabel', () => {
  it('shows both periods when both are known', () => {
    expect(periodComparisonLabel('H1 2025', 'H1 2024', 'fallback')).toBe('H1 2024 vs H1 2025')
  })

  it('shows just the prior period when only that is known', () => {
    expect(periodComparisonLabel(null, 'H1 2024', 'fallback')).toBe('vs H1 2024')
  })

  it('returns the fallback when neither period is known', () => {
    expect(periodComparisonLabel(null, null, 'vs prior period')).toBe('vs prior period')
  })
})

describe('periodContextLabel', () => {
  it('states the current period without implying a comparison', () => {
    expect(periodContextLabel('H1 2025', 'fallback')).toBe('as of H1 2025')
  })

  it('returns the fallback when the period is unknown', () => {
    expect(periodContextLabel(null, 'current count')).toBe('current count')
  })
})
