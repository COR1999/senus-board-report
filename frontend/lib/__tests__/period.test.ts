import { describe, it, expect } from 'vitest'
import { periodContextLabel } from '@/lib/period'

describe('periodContextLabel', () => {
  it('states the current period without implying a comparison', () => {
    expect(periodContextLabel('H1 2025', 'fallback')).toBe('as of H1 2025')
  })

  it('returns the fallback when the period is unknown', () => {
    expect(periodContextLabel(null, 'current count')).toBe('current count')
  })
})
