'use client'

import { Button } from '@/components/ui/button'
import { usePresentation } from './presentation-context'
import { Play } from 'lucide-react'

/**
 * "Present" button -- the only place Presentation Mode is ever started
 * from (see presentation-context.tsx's docstring for why that matters).
 * Hidden while a presentation is already active; PresentationOverlay owns
 * exit/navigation once started.
 */
export function PresentationTrigger() {
  const { active, start } = usePresentation()

  if (active) return null

  return (
    <Button variant="outline" size="sm" onClick={start} className="gap-1.5">
      <Play className="size-3.5" />
      Present
    </Button>
  )
}
