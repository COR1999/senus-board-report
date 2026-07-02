import { render } from '@testing-library/react'
import { RevenueChart } from '@/components/dashboard/revenue-chart'
import { describe, it, expect } from 'vitest'

describe('RevenueChart', () => {
  it('renders with revenue data', () => {
    const mockData = [
      { month: 'Jan', revenue: 100 },
      { month: 'Feb', revenue: 200 },
    ]

    const { container } = render(<RevenueChart data={mockData} />)

    expect(container.firstChild).toBeInTheDocument()
  })
})