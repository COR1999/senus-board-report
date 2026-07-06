import { render, screen } from '@testing-library/react'
import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { describe, it, expect, vi } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}))

describe('DashboardShell', () => {
  it('renders the title, optional description, and children', () => {
    render(
      <DashboardShell title="Reports" description="All generated board reports">
        <div>CHILD_CONTENT</div>
      </DashboardShell>
    )

    expect(screen.getByRole('heading', { name: 'Reports' })).toBeInTheDocument()
    expect(screen.getByText('All generated board reports')).toBeInTheDocument()
    expect(screen.getByText('CHILD_CONTENT')).toBeInTheDocument()
  })

  it('omits the description when none is given', () => {
    render(
      <DashboardShell title="Settings">
        <div>CHILD_CONTENT</div>
      </DashboardShell>
    )

    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.queryByText('All generated board reports')).not.toBeInTheDocument()
  })
})
