import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AiInsights } from '@/components/dashboard/ai-insights'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockMetrics = {
  revenue: { value: '€836,000', change: 38, trend: 'up' as const, history: [], available: true },
  customers: { value: '158', change: 2.5, trend: 'up' as const, history: [], available: true },
  cash: { value: '€1.2M', change: 0, trend: 'neutral' as const, history: [], available: true },
  ebitda: { value: '€150K', change: 22, trend: 'up' as const, history: [], available: true },
  ebitda_margin: { value: '18.2%', change: 3.1, trend: 'up' as const, history: [], available: true },
  cash_runway: { value: '14.5 mo', change: 20.8, trend: 'up' as const, history: [], available: true },
  interest_cover: { value: '8.4x', change: 12, trend: 'up' as const, history: [], available: true },
  roce: { value: '24.1%', change: 5.4, trend: 'up' as const, history: [], available: true },
  bookings: { value: '€700K', change: 0, trend: 'neutral' as const, history: [], available: true },
  gross_margin: { value: '61.4%', change: 2.2, trend: 'up' as const, history: [], available: true },
  operating_margin: { value: '18.2%', change: 3.1, trend: 'up' as const, history: [], available: true },
  current_period: 'Jul 2024 – Dec 2024',
  prior_period: 'Jul 2023 – Dec 2023',
  data_extracted_at: '2025-03-19T08:38:00',
  document_id: 1,
}

describe('AiInsights', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a stored result directly, with no live Gemini call at all', async () => {
    const getStoredSpy = vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue({
      report_id: 7,
      insights: [{ text: 'Stored insight text', type: 'positive', action: '', category: undefined }],
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })
    const getLiveSpy = vi.spyOn(dataService, 'getAiInsights')

    render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[]} />)

    expect(await screen.findByText('Stored insight text')).toBeInTheDocument()
    expect(getStoredSpy).toHaveBeenCalledWith(7)
    expect(getLiveSpy).not.toHaveBeenCalled()
  })

  it('falls back to a live generation and persists it when nothing is stored yet', async () => {
    vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue(null)
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue({
      insights: [{ text: 'Freshly generated insight', type: 'opportunity', action: '', category: undefined }],
      isFallback: false,
      model: 'gemini-2.5-flash',
    })
    const saveSpy = vi.spyOn(dataService, 'saveInsights').mockResolvedValue({
      report_id: 7,
      insights: [],
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })

    render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[]} />)

    expect(await screen.findByText('Freshly generated insight')).toBeInTheDocument()
    await waitFor(() =>
      expect(saveSpy).toHaveBeenCalledWith(
        7,
        [{ text: 'Freshly generated insight', type: 'opportunity', action: '', category: undefined }],
        'gemini-2.5-flash'
      )
    )
  })

  it('never persists fallback content -- a quota-exhausted result still renders but is not saved', async () => {
    vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue(null)
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue({
      insights: [{ text: 'Fallback content', type: 'positive', action: '', category: undefined }],
      isFallback: true,
      model: null,
    })
    const saveSpy = vi.spyOn(dataService, 'saveInsights')

    render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[]} />)

    expect(await screen.findByText('Fallback content')).toBeInTheDocument()
    expect(saveSpy).not.toHaveBeenCalled()
  })

  it('generates live without ever calling getStoredInsights/saveInsights when reportId is null', async () => {
    const getStoredSpy = vi.spyOn(dataService, 'getStoredInsights')
    const saveSpy = vi.spyOn(dataService, 'saveInsights')
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue({
      insights: [{ text: 'No report to anchor on yet', type: 'positive', action: '', category: undefined }],
      isFallback: false,
      model: 'gemini-2.5-flash',
    })

    render(<AiInsights metrics={mockMetrics} reportId={null} chartData={[]} />)

    expect(await screen.findByText('No report to anchor on yet')).toBeInTheDocument()
    expect(getStoredSpy).not.toHaveBeenCalled()
    expect(saveSpy).not.toHaveBeenCalled()
  })

  it('disables the refresh button once a stored result exists, with an explanatory tooltip', async () => {
    vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue({
      report_id: 7,
      insights: [{ text: 'Stored insight text', type: 'positive', action: '', category: undefined }],
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })

    render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[]} />)

    await screen.findByText('Stored insight text')
    const refreshButton = screen.getByRole('button', { name: 'Refresh AI insights' })
    expect(refreshButton).toBeDisabled()
    expect(refreshButton).toHaveAttribute('title', 'Already up to date -- upload a new report to regenerate')
  })

  it('leaves refresh enabled after a fallback result, and clicking it triggers a real second generation', async () => {
    vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue(null)
    const getLiveSpy = vi
      .spyOn(dataService, 'getAiInsights')
      .mockResolvedValueOnce({
        insights: [{ text: 'First attempt (fallback)', type: 'positive', action: '', category: undefined }],
        isFallback: true,
        model: null,
      })
      .mockResolvedValueOnce({
        insights: [{ text: 'Second attempt (real)', type: 'positive', action: '', category: undefined }],
        isFallback: false,
        model: 'gemini-2.5-flash',
      })
    const saveSpy = vi.spyOn(dataService, 'saveInsights').mockResolvedValue({
      report_id: 7,
      insights: [],
      model_version: 'gemini-2.5-flash',
      generated_at: '2026-01-01T00:00:00Z',
    })

    render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[]} />)
    await screen.findByText('First attempt (fallback)')

    const refreshButton = screen.getByRole('button', { name: 'Refresh AI insights' })
    expect(refreshButton).not.toBeDisabled()
    fireEvent.click(refreshButton)

    expect(await screen.findByText('Second attempt (real)')).toBeInTheDocument()
    expect(getLiveSpy).toHaveBeenCalledTimes(2)
    expect(saveSpy).toHaveBeenCalledWith(
      7,
      [{ text: 'Second attempt (real)', type: 'positive', action: '', category: undefined }],
      'gemini-2.5-flash'
    )
  })

  describe('folded-in historical trend', () => {
    const chartData = [
      { period: 'FY2024', revenue: 688_317, ebitda: null, cash: null, document_id: 1, cadence_months: 12 },
      { period: 'FY2025', revenue: 836_991, ebitda: null, cash: null, document_id: 2, cadence_months: 12 },
    ]

    it('appends the stored historical trend insight as a trailing Trend entry, not a separate card', async () => {
      vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue({
        report_id: 7,
        insights: [{ text: 'This report says X', type: 'positive', action: '', category: undefined }],
        model_version: 'gemini-2.5-flash',
        generated_at: '2026-01-01T00:00:00Z',
      })
      vi.spyOn(dataService, 'getStoredHistoricalInsight').mockResolvedValue({
        insight: { text: 'Across every report, revenue is up 21.6%', type: 'trend', action: '', category: undefined },
        model_version: 'gemini-2.5-flash',
        generated_at: '2026-01-01T00:00:00Z',
      })

      render(<AiInsights metrics={mockMetrics} reportId={7} chartData={chartData} />)

      expect(await screen.findByText('This report says X')).toBeInTheDocument()
      expect(await screen.findByText('Across every report, revenue is up 21.6%')).toBeInTheDocument()
      // One single card, one single heading -- not two.
      expect(screen.getAllByText('AI Board Insights')).toHaveLength(1)
      expect(screen.getByText('Trend')).toBeInTheDocument()
    })

    it('renders no trend entry at all with fewer than two real chart points', async () => {
      vi.spyOn(dataService, 'getStoredInsights').mockResolvedValue({
        report_id: 7,
        insights: [{ text: 'Only this report has anything to say', type: 'positive', action: '', category: undefined }],
        model_version: 'gemini-2.5-flash',
        generated_at: '2026-01-01T00:00:00Z',
      })
      const getStoredTrendSpy = vi.spyOn(dataService, 'getStoredHistoricalInsight')

      render(<AiInsights metrics={mockMetrics} reportId={7} chartData={[chartData[0]]} />)

      expect(await screen.findByText('Only this report has anything to say')).toBeInTheDocument()
      expect(screen.queryByText('Trend')).not.toBeInTheDocument()
      expect(getStoredTrendSpy).not.toHaveBeenCalled()
    })
  })
})
