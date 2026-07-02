import { render } from '@testing-library/react'
import { Sidebar } from "@/components/dashboard/sidebar"
import { describe, it, expect, vi } from 'vitest'

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: () => '/',
}))

describe('Sidebar', () => {
  it('renders without crashing', () => {
    const { container } = render(<Sidebar />)
    expect(container.firstChild).toBeInTheDocument()
  })
})