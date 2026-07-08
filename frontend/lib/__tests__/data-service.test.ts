import { describe, it, expect, vi, afterEach } from 'vitest'
import { uploadPDF, getAvailableExternalFilings, getMetrics, getChartData, getDashboardPeriods } from '@/lib/data-service'

function mockFetchOnce(response: { ok: boolean; statusText: string; json: () => Promise<unknown> }) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
}

describe('uploadPDF', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('surfaces the backend\'s specific detail message on failure', async () => {
    mockFetchOnce({
      ok: false,
      statusText: 'Conflict',
      json: async () => ({ detail: 'This exact file was already uploaded as document #3 on 2026-07-06.' }),
    })

    await expect(uploadPDF(new File(['x'], 'a.pdf'))).rejects.toThrow(
      'This exact file was already uploaded as document #3 on 2026-07-06.'
    )
  })

  it('falls back to a generic message when the error body has no detail field', async () => {
    mockFetchOnce({
      ok: false,
      statusText: 'Internal Server Error',
      json: async () => ({}),
    })

    await expect(uploadPDF(new File(['x'], 'a.pdf'))).rejects.toThrow(
      'Failed to upload PDF: Internal Server Error'
    )
  })

  it('falls back to a generic message when the error body is not valid JSON', async () => {
    mockFetchOnce({
      ok: false,
      statusText: 'Bad Gateway',
      json: async () => {
        throw new Error('not json')
      },
    })

    await expect(uploadPDF(new File(['x'], 'a.pdf'))).rejects.toThrow(
      'Failed to upload PDF: Bad Gateway'
    )
  })
})

describe('getAvailableExternalFilings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves to an empty list instead of throwing when the IR API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    await expect(getAvailableExternalFilings()).resolves.toEqual([])
  })
})

describe('period selector fetchers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getMetrics omits the document_id query param when not given (today\'s default "latest" behavior)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)

    await getMetrics()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/metrics\/dashboard\/summary$/),
      expect.anything()
    )
  })

  it('getMetrics appends ?document_id= when a period is selected', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)

    await getMetrics(42)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/metrics\/dashboard\/summary\?document_id=42$/),
      expect.anything()
    )
  })

  it('getChartData appends ?document_id= when a period is selected', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] })
    vi.stubGlobal('fetch', fetchMock)

    await getChartData(7)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/metrics\/dashboard\/revenue-trend\?document_id=7$/),
      expect.anything()
    )
  })

  it('getDashboardPeriods resolves to an empty list instead of throwing when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    await expect(getDashboardPeriods()).resolves.toEqual([])
  })
})
