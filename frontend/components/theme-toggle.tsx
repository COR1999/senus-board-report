'use client'

import { useEffect, useState } from 'react'
import { useTheme } from 'next-themes'
import { Sun, Moon, Monitor } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
] as const

/**
 * Light/Dark/System segmented control. Reads/writes via next-themes'
 * `useTheme`, which persists to localStorage and applies the `.dark` class
 * `globals.css`'s `@custom-variant dark` selector expects.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  // next-themes only knows the real theme after mount (it reads
  // localStorage/matchMedia client-side) -- rendering all three as
  // unselected until then avoids a server/client mismatch flash.
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    // The standard, necessary pattern for avoiding an SSR/client hydration
    // mismatch (next-themes' own docs recommend it) -- there's no
    // meaningfully different compliant alternative to "flip a flag once,
    // after mount", so this one case is deliberately exempted from the
    // set-state-in-effect rule rather than contorted around it.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true)
  }, [])

  return (
    <div className="inline-flex gap-1 rounded-lg border border-border/60 p-1" role="group" aria-label="Theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <Button
          key={value}
          type="button"
          variant="ghost"
          size="sm"
          aria-pressed={mounted && theme === value}
          className={cn(
            'gap-1.5',
            mounted && theme === value && 'bg-muted text-foreground'
          )}
          onClick={() => setTheme(value)}
        >
          <Icon className="h-4 w-4" />
          {label}
        </Button>
      ))}
    </div>
  )
}
