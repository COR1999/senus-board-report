import { render } from '@testing-library/react'
import { AiInsights } from "@/components/dashboard/ai-insights"
import { describe, it, expect } from 'vitest'

describe('AiInsights', () => {
  it('renders without crashing', () => {
    const { container } = render(< AiInsights />)
    expect(container.firstChild).toBeInTheDocument()
  })
})