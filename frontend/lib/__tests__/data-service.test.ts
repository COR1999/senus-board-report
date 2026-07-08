import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  uploadPDF,
  getAvailableExternalFilings,
  getMetrics,
  getChartData,
  getDashboardPeriods,
  getHiddenExternalFilings,
  hideExternalFiling,
  unhideExternalFiling,
  getDocument,
  approveDocument,
} from '@/lib/data-service'

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

describe('hide/unhide external filings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getHiddenExternalFilings resolves to an empty list instead of throwing when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    await expect(getHiddenExternalFilings()).resolves.toEqual([])
  })

  it('hideExternalFiling POSTs to the hide endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ attachment_id: 'agm-id', file_name: 'AGM notice', file_size: null, published_date: null }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await hideExternalFiling('agm-id')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/documents\/external\/agm-id\/hide$/),
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('unhideExternalFiling POSTs to the unhide endpoint and does not choke on an empty (204) body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 })
    vi.stubGlobal('fetch', fetchMock)

    await expect(unhideExternalFiling('agm-id')).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/documents\/external\/agm-id\/unhide$/),
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('unhideExternalFiling throws with the status text on failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, statusText: 'Not Found' }))

    await expect(unhideExternalFiling('unknown-id')).rejects.toThrow('Failed to unhide filing: Not Found')
  })
})

describe('needs_review approve workflow', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getDocument fetches the single-document detail endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 3, financial_metrics: null }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await getDocument(3)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/documents\/3$/),
      expect.anything()
    )
  })

  it('getDocument surfaces the backend\'s specific detail message on failure, not a generic one', async () => {
    mockFetchOnce({
      ok: false,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Document not found' }),
    })

    await expect(getDocument(999)).rejects.toThrow('Document not found')
  })

  it('approveDocument POSTs to the approve endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 3, financial_metrics: null }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await approveDocument(3)

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/documents\/3\/approve$/),
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('approveDocument surfaces the backend\'s specific rejection message on failure', async () => {
    mockFetchOnce({
      ok: false,
      statusText: 'Bad Request',
      json: async () => ({ detail: "This document is not pending review (tier: auto_accept) -- nothing to approve." }),
    })

    await expect(approveDocument(3)).rejects.toThrow(
      'This document is not pending review (tier: auto_accept) -- nothing to approve.'
    )
  })
})
