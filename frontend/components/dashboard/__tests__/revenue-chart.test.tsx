import { render, screen, fireEvent } from '@testing-library/react'
import { RevenueChart } from '@/components/dashboard/revenue-chart'
import { describe, it, expect } from 'vitest'

describe('RevenueChart', () => {
  it('renders with revenue data', () => {
    const mockData = [
      { period: 'Jan', revenue: 100 },
      { period: 'Feb', revenue: 200 },
    ]

    const { container } = render(<RevenueChart data={mockData} />)

    expect(container.firstChild).toBeInTheDocument()
  })

  it('shows a forecast toggle and does not crash when switched on', async () => {
    const mockData = [
      { period: 'Jan', revenue: 100 },
      { period: 'Feb', revenue: 200 },
      { period: 'Mar', revenue: 300 },
    ]
    const { container } = render(<RevenueChart data={mockData} />)

    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)

    expect(container.firstChild).toBeInTheDocument()
  })
})