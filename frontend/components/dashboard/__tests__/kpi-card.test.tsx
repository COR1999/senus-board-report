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

  it('renders neutral trend without crashing', () => {
    const { container } = render(
      <KpiCard
        title="Cash"
        value="€0"
        changePercentage={0}
        trend="neutral"
        icon={TrendingUp}
      />
    )
    expect(container.textContent).toContain('0%')
  })

  it('renders a sparkline when history has 2+ points', () => {
    const { container } = render(
      <KpiCard
        title="Revenue"
        value="€836,000"
        changePercentage={12.5}
        trend="up"
        icon={TrendingUp}
        history={[100, 200, 300]}
      />
    )
    expect(container.querySelector('.h-10.w-24')).not.toBeNull()
  })

  it('renders the hero size with larger, bolder value text and a colored icon badge', () => {
    const { container } = render(
      <KpiCard
        title="Total Revenue"
        value="€836,000"
        changePercentage={12.5}
        trend="up"
        icon={TrendingUp}
        variant="hero"
      />
    )
    expect(container.querySelector('.text-3xl')).not.toBeNull()
    expect(container.querySelector('svg.lucide-trending-up')).not.toBeNull()
  })

  it('renders the default size with the icon badge and standard value text', () => {
    const { container } = render(
      <KpiCard title="Total Revenue" value="€836,000" changePercentage={12.5} trend="up" icon={TrendingUp} />
    )
    expect(container.querySelector('.text-2xl')).not.toBeNull()
    expect(container.querySelector('svg.lucide-trending-up')).not.toBeNull()
  })

  it('colors both the value text and the icon badge by trend', () => {
    const { container: up } = render(
      <KpiCard title="Revenue" value="€500,000" changePercentage={8.3} trend="up" icon={TrendingUp} />
    )
    expect(up.querySelectorAll('.text-emerald-600').length).toBeGreaterThanOrEqual(2) // value + icon badge

    const { container: down } = render(
      <KpiCard title="EBITDA" value="-€474,000" changePercentage={-19.8} trend="down" icon={TrendingUp} />
    )
    expect(down.querySelectorAll('.text-rose-600').length).toBeGreaterThanOrEqual(2)

    const { container: neutral } = render(
      <KpiCard title="Customers" value="138" changePercentage={0} trend="neutral" icon={TrendingUp} />
    )
    expect(neutral.querySelector('.text-foreground')).not.toBeNull()
  })

  it('renders no sparkline when history is omitted, empty, or single-point', () => {
    const { container: noHistory } = render(
      <KpiCard title="Revenue" value="€836,000" changePercentage={12.5} trend="up" icon={TrendingUp} />
    )
    expect(noHistory.querySelector('.h-10.w-24')).toBeNull()

    const { container: emptyHistory } = render(
      <KpiCard title="Revenue" value="€836,000" changePercentage={12.5} trend="up" icon={TrendingUp} history={[]} />
    )
    expect(emptyHistory.querySelector('.h-10.w-24')).toBeNull()

    const { container: singlePoint } = render(
      <KpiCard title="Revenue" value="€836,000" changePercentage={12.5} trend="up" icon={TrendingUp} history={[100]} />
    )
    expect(singlePoint.querySelector('.h-10.w-24')).toBeNull()
  })
})