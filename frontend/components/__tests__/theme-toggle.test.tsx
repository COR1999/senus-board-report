import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeToggle } from '@/components/theme-toggle'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const setTheme = vi.fn()
let currentTheme = 'system'

vi.mock('next-themes', () => ({
  useTheme: () => ({ theme: currentTheme, setTheme }),
}))

describe('ThemeToggle', () => {
  beforeEach(() => {
    setTheme.mockClear()
    currentTheme = 'system'
  })

  it('renders Light, Dark, and System options', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: /light/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dark/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /system/i })).toBeInTheDocument()
  })

  it('calls setTheme with the clicked option', () => {
    render(<ThemeToggle />)
    fireEvent.click(screen.getByRole('button', { name: /dark/i }))
    expect(setTheme).toHaveBeenCalledWith('dark')
  })

  it('marks the active theme as pressed once mounted', async () => {
    currentTheme = 'dark'
    render(<ThemeToggle />)
    expect(await screen.findByRole('button', { name: /dark/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /light/i })).toHaveAttribute('aria-pressed', 'false')
  })
})
