import { render, screen, fireEvent } from '@testing-library/react'
import { AiInsights } from '@/components/dashboard/ai-insights'
import * as dataService from '@/lib/data-service'
import { resetInsightsCache } from '@/lib/insights-cache'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockMetrics = {
  revenue: { value: '€836,000', change: 38, trend: 'up' as const, history: [] },
  customers: { value: '158', change: 2.5, trend: 'up' as const, history: [] },
  cash: { value: '€1.2M', change: 0, trend: 'neutral' as const, history: [] },
  ebitda: { value: '€150K', change: 22, trend: 'up' as const, history: [] },
  ebitda_margin: { value: '18.2%', change: 3.1, trend: 'up' as const, history: [] },
  cash_runway: { value: '14.5 mo', change: 20.8, trend: 'up' as const, history: [] },
  interest_cover: { value: '8.4x', change: 12, trend: 'up' as const, history: [] },
  roce: { value: '24.1%', change: 5.4, trend: 'up' as const, history: [] },
  bookings: { value: '€700K', change: 0, trend: 'neutral' as const, history: [] },
  current_period: 'Jul 2024 – Dec 2024',
  prior_period: 'Jul 2023 – Dec 2023',
  data_extracted_at: '2025-03-19T08:38:00',
  document_id: 1,
}

const mockMetricsAfterNewUpload = {
  ...mockMetrics,
  revenue: { value: '€1,050,000', change: 25.5, trend: 'up' as const, history: [] },
  current_period: 'Jul 2025 – Dec 2025',
  prior_period: 'Jul 2024 – Dec 2024',
}

describe('AiInsights', () => {
  beforeEach(() => {
    // The insights cache is module-level, not component state (see
    // lib/insights-cache.ts) -- reset it so one test's cached result doesn't
    // leak into the next, since vitest doesn't reset modules between `it()`
    // blocks by default.
    resetInsightsCache()
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue({
      insights: [
        { text: 'ANY_INSIGHT_TEXT', type: 'positive', action: 'ANY_ACTION_TEXT', category: 'Growth & Revenue' },
      ],
      isFallback: false,
    })
  })

  // No `clearMocks` in vitest.config.ts, so spy call counts otherwise leak
  // across tests in this file (same issue found in feature/document-report-
  // actions) -- several tests below assert exact call counts.
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders without crashing', () => {
    const { container } = render(<AiInsights metrics={mockMetrics} />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('renders fetched insights with a type badge', async () => {
    render(<AiInsights metrics={mockMetrics} />)
    expect(await screen.findByText('ANY_INSIGHT_TEXT')).toBeInTheDocument()
    expect(await screen.findByText('Positive')).toBeInTheDocument()
  })

  it('renders the category caption and recommended action alongside the observation', async () => {
    render(<AiInsights metrics={mockMetrics} />)
    expect(await screen.findByText('ANY_INSIGHT_TEXT')).toBeInTheDocument()
    expect(screen.getByText('Growth & Revenue')).toBeInTheDocument()
    expect(screen.getByText('ANY_ACTION_TEXT')).toBeInTheDocument()
  })

  it('disables the refresh button once insights exist for the current data, and blocks a click from re-firing', async () => {
    // A time-based cooldown alone still lets a user re-spend quota
    // re-analyzing data that hasn't changed. The real guard is "has a new
    // report actually landed since the last generation" -- if not, the
    // button stays disabled regardless of how much time has passed.
    render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('ANY_INSIGHT_TEXT')
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)

    const button = screen.getByRole('button', { name: 'Refresh AI insights' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Already up to date -- upload a new report to regenerate')

    fireEvent.click(button)
    fireEvent.click(button)

    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)
  })

  it('does not re-fetch insights on a re-render with the same metrics reference', async () => {
    // This is what makes background polling (useAsyncData's pollIntervalMs)
    // safe: a poll that returns unchanged content keeps the same object
    // reference, so re-rendering with it must not trigger another Gemini
    // call -- only a *genuinely new* metrics object should.
    const { rerender } = render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('ANY_INSIGHT_TEXT')
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)

    rerender(<AiInsights metrics={mockMetrics} />)

    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)
  })

  it('generates fresh insights reflecting a new document/report, not the old ones', async () => {
    // Simulates the real end-to-end path: a new PDF is uploaded -> the
    // backend extracts new metrics -> the dashboard's data layer eventually
    // hands AiInsights a genuinely new `metrics` object (today: on
    // remount/navigation; with feature/ai-insights-auto-refresh merged in:
    // automatically, via polling). Whatever delivers the new object, this
    // is the contract AiInsights must honor: a new object -> a new Gemini
    // call built from the new numbers, not a replay of the old commentary.
    vi.spyOn(dataService, 'getAiInsights')
      .mockResolvedValueOnce({
        insights: [{ text: 'OLD_INSIGHT_TEXT', type: 'positive', action: 'OLD_ACTION_TEXT' }],
        isFallback: false,
      })
      .mockResolvedValueOnce({
        insights: [{ text: 'NEW_INSIGHT_TEXT', type: 'opportunity', action: 'NEW_ACTION_TEXT' }],
        isFallback: false,
      })

    const { rerender } = render(<AiInsights metrics={mockMetrics} />)
    expect(await screen.findByText('OLD_INSIGHT_TEXT')).toBeInTheDocument()
    expect(dataService.getAiInsights).toHaveBeenCalledWith(mockMetrics)

    rerender(<AiInsights metrics={mockMetricsAfterNewUpload} />)

    expect(await screen.findByText('NEW_INSIGHT_TEXT')).toBeInTheDocument()
    expect(screen.queryByText('OLD_INSIGHT_TEXT')).not.toBeInTheDocument()
    expect(dataService.getAiInsights).toHaveBeenLastCalledWith(mockMetricsAfterNewUpload)
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(2)

    // And once the new data has been analyzed, the button locks again --
    // there's nothing newer to regenerate from until another report arrives.
    const button = screen.getByRole('button', { name: 'Refresh AI insights' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(2)
  })

  it('keeps the refresh button enabled after a fallback result, instead of treating it as up to date', async () => {
    // Real production bug: a quota-exhausted/failed Gemini call previously
    // got cached identically to a real success, permanently disabling
    // refresh for that data even though nothing real was ever generated --
    // see getAiInsights' own docstring in data-service.ts.
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue({
      insights: [{ text: 'FALLBACK_TEXT', type: 'positive', action: '' }],
      isFallback: true,
    })

    render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('FALLBACK_TEXT')

    const button = screen.getByRole('button', { name: 'Refresh AI insights' })
    expect(button).not.toBeDisabled()
  })

  it('does not re-fetch after unmount/remount with unchanged data (e.g. navigating away and back)', async () => {
    // Regression test: AiInsights only lives on the dashboard route, so
    // visiting another page (Settings to change the theme, Reports,
    // Documents) and returning unmounts and remounts it. A per-instance
    // guard would reset on that remount and trigger a wasted,
    // non-deterministic Gemini call even though the underlying report data
    // hasn't changed -- the module-level cache in lib/insights-cache.ts must
    // survive that remount.
    const { unmount } = render(<AiInsights metrics={mockMetrics} />)
    expect(await screen.findByText('ANY_INSIGHT_TEXT')).toBeInTheDocument()
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)

    unmount()
    render(<AiInsights metrics={mockMetrics} />)

    expect(await screen.findByText('ANY_INSIGHT_TEXT')).toBeInTheDocument()
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)
  })
})
