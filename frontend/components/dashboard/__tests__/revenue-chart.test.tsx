import { render, screen, fireEvent } from '@testing-library/react'
import { RevenueChart } from '@/components/dashboard/revenue-chart'
import { describe, it, expect } from 'vitest'

const mockData = [
  { period: 'Jan', revenue: 100, ebitda: -10, cash: 50 },
  { period: 'Feb', revenue: 200, ebitda: -5, cash: 60 },
  { period: 'Mar', revenue: 300, ebitda: 5, cash: 70 },
]

describe('RevenueChart', () => {
  it('renders with revenue data', () => {
    const { container } = render(<RevenueChart data={mockData} />)

    expect(container.firstChild).toBeInTheDocument()
    expect(screen.getByText('Revenue Trend')).toBeInTheDocument()
  })

  it('shows a forecast toggle and does not crash when switched on', async () => {
    const { container } = render(<RevenueChart data={mockData} />)

    const toggle = screen.getByRole('switch')
    fireEvent.click(toggle)

    expect(container.firstChild).toBeInTheDocument()
  })

  it('swaps to EBITDA and keeps the forecast toggle available', () => {
    const { container } = render(<RevenueChart data={mockData} />)

    fireEvent.click(screen.getByRole('button', { name: 'EBITDA' }))
    expect(screen.getByText('EBITDA Trend')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('switch'))
    expect(container.firstChild).toBeInTheDocument()
  })

  it('swaps to Cash and back to Revenue', () => {
    render(<RevenueChart data={mockData} />)

    fireEvent.click(screen.getByRole('button', { name: 'Cash' }))
    expect(screen.getByText('Cash Trend')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Revenue' }))
    expect(screen.getByText('Revenue Trend')).toBeInTheDocument()
  })
})
