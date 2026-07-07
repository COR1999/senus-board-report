import { render, screen, fireEvent } from '@testing-library/react'
import { AiInsights } from '@/components/dashboard/ai-insights'
import * as dataService from '@/lib/data-service'
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
  current_period: 'H1 2025',
  prior_period: 'H1 2024',
}

const mockMetricsAfterNewUpload = {
  ...mockMetrics,
  revenue: { value: '€1,050,000', change: 25.5, trend: 'up' as const, history: [] },
  current_period: 'H1 2026',
  prior_period: 'H1 2025',
}

describe('AiInsights', () => {
  beforeEach(() => {
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue([
      { text: 'ANY_INSIGHT_TEXT', type: 'positive' },
    ])
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
      .mockResolvedValueOnce([{ text: 'OLD_INSIGHT_TEXT', type: 'positive' }])
      .mockResolvedValueOnce([{ text: 'NEW_INSIGHT_TEXT', type: 'opportunity' }])

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
})
