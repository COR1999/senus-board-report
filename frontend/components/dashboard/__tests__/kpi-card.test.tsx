import { render, screen } from '@testing-library/react'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { TrendingUp } from 'lucide-react'
import { describe, it, expect } from 'vitest'

describe('KpiCard', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <KpiCard
        title="Total Revenue"
        value="€836,000"
        changePercentage={12.5}
        trend="up"
        icon={TrendingUp}
      />
    )
    expect(container.firstChild).toBeInTheDocument()
  })

  it('displays title and value', () => {
    const { container } = render(
      <KpiCard
        title="Total Revenue"
        value="€836,000"
        changePercentage={12.5}
        trend="up"
        icon={TrendingUp}
      />
    )
    expect(container.textContent).toContain('Total Revenue')
    expect(container.textContent).toContain('€836,000')
  })

  it('displays positive trend with percentage', () => {
    const { container } = render(
      <KpiCard
        title="Revenue"
        value="€500,000"
        changePercentage={8.3}
        trend="up"
        icon={TrendingUp}
      />
    )
    expect(container.textContent).toContain('8.3%')
  })

  it('displays negative trend', () => {
    const { container } = render(
      <KpiCard
        title="Expenses"
        value="€100,000"
        changePercentage={5.2}
        trend="down"
        icon={TrendingUp}
      />
    )
    expect(container.textContent).toContain('5.2%')
  })

  it('displays custom timeframe', () => {
    const { container } = render(
      <KpiCard
        title="Revenue"
        value="€836,000"
        changePercentage={12.5}
        trend="up"
        icon={TrendingUp}
        timeframe="vs target"
      />
    )
    expect(container.textContent).toContain('vs target')
  })
})