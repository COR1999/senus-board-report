import { render, screen } from '@testing-library/react'
import SettingsPage from '@/app/settings/page'
import { describe, it, expect, vi } from 'vitest'

vi.mock('next/navigation', () => ({
  usePathname: () => '/settings',
}))

describe('SettingsPage', () => {
  it('renders the placeholder profile section', () => {
    render(<SettingsPage />)
    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument()
    // Appears twice: once in the sidebar's footer profile, once in the settings card.
    expect(screen.getAllByText('Sarah Jenkins').length).toBeGreaterThan(0)
  })
})
