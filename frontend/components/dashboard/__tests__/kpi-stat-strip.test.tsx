import { render, screen } from '@testing-library/react'
import { KpiStatStrip, type StatStripItem } from '@/components/dashboard/kpi-stat-strip'
import { describe, it, expect } from 'vitest'

const items: StatStripItem[] = [
  { key: 'bookings', category: 'Growth & Revenue', label: 'Bookings', value: '€700K', changePercentage: 0, trend: 'neutral' },
  { key: 'ebitda_margin', category: 'Profitability', label: 'EBITDA Margin', value: '18.2%', changePercentage: 3.1, trend: 'up' },
  { key: 'cash_runway', category: 'Cash & Liquidity', label: 'Cash Runway', value: '14.5 mo', changePercentage: 20.8, trend: 'up' },
  { key: 'interest_cover', category: 'Solvency & Leverage', label: 'Interest Cover', value: '8.4x', changePercentage: 12, trend: 'up' },
  { key: 'roce', category: 'Returns', label: 'ROCE', value: '24.1%', changePercentage: 5.4, trend: 'up' },
]

describe('KpiStatStrip', () => {
  it('renders every item with its category, label, value, and delta', () => {
    render(<KpiStatStrip items={items} />)

    for (const item of items) {
      expect(screen.getByText(item.category)).toBeInTheDocument()
      expect(screen.getByText(item.label)).toBeInTheDocument()
      expect(screen.getByText(item.value)).toBeInTheDocument()
    }
    expect(screen.getByText('3.1%')).toBeInTheDocument()
  })

  it('omits sparklines -- this is a compact, decoration-free strip', () => {
    const { container } = render(<KpiStatStrip items={items} />)
    // Trend arrow icons are small svgs too, so check for the absence of a
    // Recharts chart wrapper specifically, not "no svg at all".
    expect(container.querySelector('.recharts-responsive-container')).toBeNull()
  })

  it('colors the value text by trend, not just the small delta pill', () => {
    const { container } = render(<KpiStatStrip items={items} />)
    // EBITDA Margin is trend "up" -- its value should carry the trend color.
    expect(container.querySelector('.text-emerald-600')).not.toBeNull()
  })
})
