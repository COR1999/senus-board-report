import { render, screen } from '@testing-library/react'
import { AiInsights } from '@/components/dashboard/ai-insights'
import * as dataService from '@/lib/data-service'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockMetrics = {
  revenue: { value: '€836,000', change: 38, trend: 'up' as const },
  customers: { value: '158', change: 2.5, trend: 'up' as const },
  cash: { value: '€1.2M', change: 0, trend: 'up' as const },
  ebitda: { value: '€150K', change: 22, trend: 'up' as const },
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
