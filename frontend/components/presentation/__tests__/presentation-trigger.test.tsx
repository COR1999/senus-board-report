import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { PresentationProvider } from '@/components/presentation/presentation-context'
import { PresentationTrigger } from '@/components/presentation/presentation-trigger'
import type { PresentationStep } from '@/lib/presentation/steps'

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}))

const TEST_STEPS: PresentationStep[] = [
  { id: 'step-a', page: '/', title: 'Step A', subtitle: 'a', talkingPoint: 'ask a' },
]

describe('PresentationTrigger', () => {
  it('renders a Present button when inactive, and starts the tour on click', () => {
    render(
      <PresentationProvider allSteps={TEST_STEPS}>
        <div id="step-a">A content</div>
        <PresentationTrigger />
      </PresentationProvider>
    )

    const button = screen.getByRole('button', { name: /present/i })
    expect(button).toBeInTheDocument()

    fireEvent.click(button)

    // Once active, the trigger itself hides (PresentationOverlay owns
    // exit/navigation from here) -- the button is gone from the DOM.
    expect(screen.queryByRole('button', { name: /present/i })).not.toBeInTheDocument()
  })
})
