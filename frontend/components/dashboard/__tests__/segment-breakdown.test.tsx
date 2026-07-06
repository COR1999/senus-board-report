import { render } from '@testing-library/react'
import { SegmentBreakdown } from '@/components/dashboard/segment-breakdown'
import { describe, it, expect } from 'vitest'

describe('SegmentBreakdown', () => {
  const data = [
    { segment: 'Corporate', value: 500000, percentage: 60 },
    { segment: 'Government', value: 250000, percentage: 30 },
    { segment: 'Agriculture', value: 84000, percentage: 10 },
  ]

  it('renders without crashing', () => {
    const { container } = render(<SegmentBreakdown data={data} />)
    expect(container.firstChild).toBeInTheDocument()
  })

  it('shows a direct label for every segment (not color-alone identity)', () => {
    const { container } = render(<SegmentBreakdown data={data} />)
    expect(container.textContent).toContain('Corporate · 60%')
    expect(container.textContent).toContain('Government · 30%')
    expect(container.textContent).toContain('Agriculture · 10%')
  })
})
