import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const generateContent = vi.fn()

// A plain arrow function can't be used as a mock constructor (Vitest/Node
// throws "is not a constructor" the moment the route does `new GoogleGenAI(...)`)
// -- a real class is required here.
class MockGoogleGenAI {
  models = { generateContent }
}

vi.mock('@google/genai', () => ({
  GoogleGenAI: MockGoogleGenAI,
}))

const ORIGINAL_ENV = process.env.GEMINI_INSIGHTS_API_KEY

function makeRequest(): Request {
  return new Request('http://localhost/api/insights', {
    method: 'POST',
    body: JSON.stringify({
      metrics: {
        revenue: { value: '€836,000', change: 38, trend: 'up', history: [] },
        current_period: 'Jul 2025 – Dec 2025',
        prior_period: null,
        data_extracted_at: null,
      },
    }),
  })
}

describe('POST /api/insights', () => {
  beforeEach(async () => {
    process.env.GEMINI_INSIGHTS_API_KEY = 'test-key'
    generateContent.mockReset()
    const { _resetGeminiBackoffForTests } = await import('@/app/api/insights/route')
    _resetGeminiBackoffForTests()
  })

  afterEach(() => {
    process.env.GEMINI_INSIGHTS_API_KEY = ORIGINAL_ENV
    vi.useRealTimers()
  })

  it('returns fallback insights and never calls Gemini when no API key is configured', async () => {
    delete process.env.GEMINI_INSIGHTS_API_KEY
    const { POST } = await import('@/app/api/insights/route')

    const res = await POST(makeRequest())
    const body = await res.json()

    expect(body.insights.length).toBeGreaterThan(0)
    expect(body.isFallback).toBe(true)
    expect(generateContent).not.toHaveBeenCalled()
  })

  it('returns real insights on a successful Gemini call, with isFallback: false', async () => {
    generateContent.mockResolvedValue({
      text: JSON.stringify({ insights: [{ text: 'Real insight', type: 'positive' }] }),
    })
    const { POST } = await import('@/app/api/insights/route')

    const res = await POST(makeRequest())
    const body = await res.json()

    expect(body.insights).toEqual([{ text: 'Real insight', type: 'positive', action: '', category: undefined }])
    expect(body.isFallback).toBe(false)
  })

  it('returns isFallback: true when Gemini fails, so callers never treat placeholder content as real', async () => {
    generateContent.mockRejectedValue(new Error('some transient failure'))
    const { POST } = await import('@/app/api/insights/route')

    const res = await POST(makeRequest())
    const body = await res.json()

    expect(body.isFallback).toBe(true)
  })

  it('backs off for 60s after a rate-limit (429) error, skipping Gemini entirely on the next call', async () => {
    vi.useFakeTimers()
    generateContent.mockRejectedValue(new Error('429 RESOURCE_EXHAUSTED. quota exceeded'))
    const { POST } = await import('@/app/api/insights/route')

    const first = await POST(makeRequest())
    expect((await first.json()).insights.length).toBeGreaterThan(0)
    expect(generateContent).toHaveBeenCalledTimes(1)

    // Still within the 60s backoff window -- must not call Gemini again.
    vi.advanceTimersByTime(30_000)
    await POST(makeRequest())
    expect(generateContent).toHaveBeenCalledTimes(1)

    // Backoff has cleared -- the next call should try Gemini again.
    vi.advanceTimersByTime(31_000)
    generateContent.mockResolvedValue({ text: JSON.stringify({ insights: [{ text: 'Back', type: 'positive' }] }) })
    await POST(makeRequest())
    expect(generateContent).toHaveBeenCalledTimes(2)
  })

  it('backs off for 24h after a billing/prepayment-exhausted error, not the short 60s window', async () => {
    vi.useFakeTimers()
    generateContent.mockRejectedValue(
      new Error("429 RESOURCE_EXHAUSTED. Your prepayment credits are depleted. Please go to AI Studio...")
    )
    const { POST } = await import('@/app/api/insights/route')

    await POST(makeRequest())
    expect(generateContent).toHaveBeenCalledTimes(1)

    // Well past the short rate-limit window, but nowhere near 24h --
    // billing exhaustion must not clear early.
    vi.advanceTimersByTime(61_000)
    await POST(makeRequest())
    expect(generateContent).toHaveBeenCalledTimes(1)
  })
})
