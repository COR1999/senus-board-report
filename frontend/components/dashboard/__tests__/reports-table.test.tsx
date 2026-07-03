import { render } from '@testing-library/react'
import { ReportsTable } from '@/components/dashboard/reports-table'
import { describe, it, expect } from 'vitest'

describe('ReportsTable', () => {
  it('renders without crashing', () => {
    const { container } = render(<ReportsTable />)
    expect(container.firstChild).toBeInTheDocument()
  })
})