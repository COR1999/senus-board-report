import { render, screen } from '@testing-library/react'
import { HistoricalTrendInsight } from '@/components/dashboard/historical-trend-insight'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, afterEach } from 'vitest'
import type { ChartDataPoint } from '@/lib/data-service'

const twoPoints: ChartDataPoint[] = [
  { period: 'FY2024', revenue: 700_000, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
  { period: 'FY2025', revenue: 836_991, ebitda: null, cash: null, document_id: 2, cadence_months: 12 },
]

describe('HistoricalTrendInsight', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders nothing with fewer than 2 real points -- nothing meaningful to say yet', () => {
    const { container } = render(<HistoricalTrendInsight chartData={[twoPoints[0]]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a stored insight directly, with no live Gemini call at all', async () => {
    const getStoredSpy = vi.spyOn(dataService, 'getStoredHistoricalInsight').mockResolvedValue({
      insight: { text: 'Revenue has grown steadily FY24->FY25', type: 'trend', action: '', category: undefined },
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })
    const getLiveSpy = vi.spyOn(dataService, 'getHistoricalTrendInsight')

    render(<HistoricalTrendInsight chartData={twoPoints} />)

    expect(await screen.findByText('Revenue has grown steadily FY24->FY25')).toBeInTheDocument()
    expect(getStoredSpy).toHaveBeenCalled()
    expect(getLiveSpy).not.toHaveBeenCalled()
  })

  it('falls back to a live generation and persists it when nothing is stored yet', async () => {
    vi.spyOn(dataService, 'getStoredHistoricalInsight').mockResolvedValue(null)
    vi.spyOn(dataService, 'getHistoricalTrendInsight').mockResolvedValue({
      insights: [{ text: 'Freshly generated trend insight', type: 'trend', action: '', category: undefined }],
      isFallback: false,
      model: 'gemini-2.5-flash',
    })
    const saveSpy = vi.spyOn(dataService, 'saveHistoricalInsight').mockResolvedValue({
      insight: { text: 'Freshly generated trend insight', type: 'trend', action: '', category: undefined },
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })

    render(<HistoricalTrendInsight chartData={twoPoints} />)

    expect(await screen.findByText('Freshly generated trend insight')).toBeInTheDocument()
    expect(saveSpy).toHaveBeenCalledWith(
      { text: 'Freshly generated trend insight', type: 'trend', action: '', category: undefined },
      'gemini-2.5-flash'
    )
  })

  it('never persists fallback content', async () => {
    vi.spyOn(dataService, 'getStoredHistoricalInsight').mockResolvedValue(null)
    vi.spyOn(dataService, 'getHistoricalTrendInsight').mockResolvedValue({
      insights: [{ text: 'Fallback trend text', type: 'trend', action: '', category: undefined }],
      isFallback: true,
      model: null,
    })
    const saveSpy = vi.spyOn(dataService, 'saveHistoricalInsight')

    render(<HistoricalTrendInsight chartData={twoPoints} />)

    expect(await screen.findByText('Fallback trend text')).toBeInTheDocument()
    expect(saveSpy).not.toHaveBeenCalled()
  })
})
