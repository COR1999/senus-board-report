import { render } from '@testing-library/react'
import { KpiSparkline } from '@/components/dashboard/kpi-sparkline'
import { describe, it, expect } from 'vitest'

describe('KpiSparkline', () => {
  it('renders a container when given 2+ points', () => {
    const { container } = render(<KpiSparkline history={[10, 20, 30]} trend="up" />)
    expect(container.firstChild).not.toBeNull()
  })

  it('renders nothing for fewer than 2 points', () => {
    const { container: empty } = render(<KpiSparkline history={[]} trend="up" />)
    expect(empty.firstChild).toBeNull()

    const { container: single } = render(<KpiSparkline history={[10]} trend="up" />)
    expect(single.firstChild).toBeNull()
  })

  it('drops null entries rather than plotting them as 0', () => {
    // Only 2 real points here (10, 30) once the null is dropped -- still chartable.
    const { container } = render(<KpiSparkline history={[10, null, 30]} trend="up" />)
    expect(container.firstChild).not.toBeNull()
  })

  it('treats an all-but-one-null history as insufficient data', () => {
    const { container } = render(<KpiSparkline history={[null, null, 10]} trend="up" />)
    expect(container.firstChild).toBeNull()
  })
})
