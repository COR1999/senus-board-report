import { render, screen } from '@testing-library/react'
import { AiInsights } from '@/components/dashboard/ai-insights'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

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
}

describe('AiInsights', () => {
  beforeEach(() => {
    vi.spyOn(dataService, 'getAiInsights').mockResolvedValue([
      { text: 'ANY_INSIGHT_TEXT', type: 'positive' },
    ])
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
})
