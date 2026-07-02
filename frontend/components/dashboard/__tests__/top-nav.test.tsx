import { render } from '@testing-library/react'
import { TopNav } from "@/components/dashboard/top-nav"
import { describe, it, expect } from 'vitest'

describe('TopNav', () => {
  it('renders without crashing', () => {
    const { container } = render(<TopNav />)
    expect(container.firstChild).toBeInTheDocument()
  })
})