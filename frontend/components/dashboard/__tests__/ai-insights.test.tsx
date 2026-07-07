import { render, screen, fireEvent, act } from '@testing-library/react'
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
  // across tests in this file -- several tests below assert exact counts.
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
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

  it('re-fetches insights (a real call, same data path as the initial load) when the refresh button is clicked', async () => {
    render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('ANY_INSIGHT_TEXT')
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(1)
    expect(dataService.getAiInsights).toHaveBeenCalledWith(mockMetrics)

    fireEvent.click(screen.getByRole('button', { name: 'Refresh AI insights' }))

    await vi.waitFor(() => expect(dataService.getAiInsights).toHaveBeenCalledTimes(2))
    expect(dataService.getAiInsights).toHaveBeenLastCalledWith(mockMetrics)
  })

  it('disables the refresh button during the cooldown, then re-enables it', async () => {
    // Let the initial mount load finish under real timers first -- the
    // button starts disabled while that's in flight, and enabling fake
    // timers before it resolves stalls the mocked promise's microtask
    // flush along with it, leaving the click below silently ignored.
    render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('ANY_INSIGHT_TEXT')

    vi.useFakeTimers({ shouldAdvanceTime: true })
    const button = screen.getByRole('button', { name: 'Refresh AI insights' })

    await act(async () => {
      fireEvent.click(button)
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(dataService.getAiInsights).toHaveBeenCalledTimes(2)
    expect(button).toBeDisabled()

    await act(async () => {
      vi.advanceTimersByTime(30_000)
    })

    expect(button).not.toBeDisabled()
  })

  it('does not spam-trigger extra calls while the cooldown is active', async () => {
    render(<AiInsights metrics={mockMetrics} />)
    await screen.findByText('ANY_INSIGHT_TEXT')

    vi.useFakeTimers({ shouldAdvanceTime: true })
    const button = screen.getByRole('button', { name: 'Refresh AI insights' })

    await act(async () => {
      fireEvent.click(button)
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(2)

    // Rapid re-clicks while disabled/on cooldown must not fire more calls --
    // each real call spends Gemini's free-tier quota, not a free UI action.
    fireEvent.click(button)
    fireEvent.click(button)
    expect(dataService.getAiInsights).toHaveBeenCalledTimes(2)
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
  })
})
