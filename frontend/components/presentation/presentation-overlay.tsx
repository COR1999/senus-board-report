'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { usePresentation } from './presentation-context'
import { ChevronLeft, ChevronRight, Loader2, MessageCircleQuestion, X } from 'lucide-react'

const PANEL_WIDTH = 380
const FALLBACK_PANEL_HEIGHT = 320
const GAP = 16
const VIEWPORT_MARGIN = 16
// However tall the panel actually is, `top` is clamped so at least this
// much of it -- header + footer, the parts that actually matter -- stays
// on screen. Combined with the panel's own max-height/overflow, this is
// what guarantees Next/Back are always reachable rather than getting
// pushed below the viewport.
const MIN_VISIBLE_HEIGHT = 160
// Belt-and-braces on top of the scroll/resize listeners below: a table
// gaining a row after a live upload, a banner appearing/disappearing, or
// any other React-driven layout shift doesn't fire either of those native
// events, so polling is what actually catches it and self-corrects
// (confirmed directly: the panel was left overlapping the Documents table
// after its row count changed mid-step, with neither scroll nor resize
// ever firing).
const POLL_INTERVAL_MS = 250

interface Position {
  top: number
  left: number
}

function clampPosition(top: number, left: number, panelHeight: number): Position {
  return {
    top: Math.min(
      Math.max(top, VIEWPORT_MARGIN),
      window.innerHeight - VIEWPORT_MARGIN - Math.min(panelHeight, MIN_VISIBLE_HEIGHT)
    ),
    left: Math.min(Math.max(left, VIEWPORT_MARGIN), window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN),
  }
}

/** Positions the panel just below (or, if there's no room, above) the
 * currently highlighted section -- polled continuously (see
 * POLL_INTERVAL_MS) plus recomputed on scroll/resize, so the panel tracks
 * the highlight instead of sitting in one fixed spot that ends up covering
 * whatever it's supposed to be pointing at. Uses the panel's own measured
 * height (via `panelRef`) once available, not a hardcoded guess -- an
 * estimate that's too small is exactly what caused the button row to be
 * positioned off-screen before this. Falls back to a fixed bottom-right
 * position if the target element can't be found (e.g. mid-navigation,
 * briefly). */
function usePanelPosition(elementId: string | null, panelRef: React.RefObject<HTMLDivElement | null>): Position {
  // Lazy initializer, not a plain expression -- `window` doesn't exist
  // during Next.js's server render pass, even for a 'use client' component
  // (it still renders once server-side for the initial HTML). A plain
  // `useState({ top: window.innerHeight - ... })` argument gets evaluated
  // on every render regardless of whether React uses the result, which
  // throws immediately server-side; the function form only ever runs
  // client-side, on mount.
  const [position, setPosition] = useState<Position>(() =>
    typeof window === 'undefined'
      ? { top: 0, left: 0 }
      : clampPosition(
          window.innerHeight - FALLBACK_PANEL_HEIGHT - VIEWPORT_MARGIN,
          window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN,
          FALLBACK_PANEL_HEIGHT
        )
  )

  useEffect(() => {
    if (!elementId) return

    function recompute() {
      const panelHeight = panelRef.current?.getBoundingClientRect().height || FALLBACK_PANEL_HEIGHT
      const el = document.getElementById(elementId as string)
      if (!el) {
        setPosition(
          clampPosition(
            window.innerHeight - panelHeight - VIEWPORT_MARGIN,
            window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN,
            panelHeight
          )
        )
        return
      }
      const rect = el.getBoundingClientRect()
      const roomBelow = window.innerHeight - rect.bottom
      const placeBelow = roomBelow >= panelHeight + GAP
      const top = placeBelow ? rect.bottom + GAP : rect.top - panelHeight - GAP
      setPosition(clampPosition(top, rect.left, panelHeight))
    }

    recompute()
    window.addEventListener('scroll', recompute, true)
    window.addEventListener('resize', recompute)
    const interval = setInterval(recompute, POLL_INTERVAL_MS)
    return () => {
      window.removeEventListener('scroll', recompute, true)
      window.removeEventListener('resize', recompute)
      clearInterval(interval)
    }
  }, [elementId, panelRef])

  return position
}

/**
 * The floating control panel shown while Presentation Mode is active --
 * title/subtitle/talking-point of the current step in a scrollable content
 * area, with a Prev/Next/Exit footer (mirrored by the arrow-key/Escape
 * bindings in PresentationProvider) that's never scrolled out of view --
 * the footer is what actually matters for being able to continue the
 * tour, so it's pinned regardless of how tall the content above it gets.
 * Tracks near the highlighted section rather than sitting fixed on screen
 * (see usePanelPosition). Renders nothing while inactive, so this can be
 * mounted unconditionally once in the root layout.
 */
export function PresentationOverlay() {
  const { active, currentStep, stepNumber, totalSteps, isFirstStep, isLastStep, processingLabel, next, prev, stop } =
    usePresentation()
  const panelRef = useRef<HTMLDivElement>(null)
  const position = usePanelPosition(currentStep?.id ?? null, panelRef)

  if (!active || !currentStep) return null

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-label="Presentation mode"
      className="fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-border/60 bg-card/95 shadow-2xl backdrop-blur transition-[top,left] duration-300 ease-out"
      style={{
        top: position.top,
        left: position.left,
        width: PANEL_WIDTH,
        maxHeight: `calc(100vh - ${VIEWPORT_MARGIN * 2}px)`,
      }}
    >
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-medium tracking-wide text-emerald-500 uppercase">
              Presenting · {stepNumber} / {totalSteps}
            </p>
            <h2 className="truncate text-base font-semibold text-foreground">{currentStep.title}</h2>
            <p className="text-sm text-muted-foreground">{currentStep.subtitle}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={stop}
            aria-label="Exit presentation"
            className="shrink-0 text-muted-foreground"
          >
            <X className="size-4" />
          </Button>
        </div>

        <div className="mt-2.5 flex items-center gap-1.5">
          <MessageCircleQuestion className="size-3.5 shrink-0 text-indigo-500" />
          <p className="text-xs text-indigo-600 dark:text-indigo-400">{currentStep.talkingPoint}</p>
        </div>

        {processingLabel && (
          <div
            className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-600 dark:text-emerald-400"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="size-4 animate-spin" />
            {processingLabel}
          </div>
        )}
      </div>

      {!processingLabel && (
        <div className="flex shrink-0 items-center justify-between gap-4 border-t border-border/60 p-4">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {Array.from({ length: totalSteps }, (_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all ${
                  i === stepNumber - 1 ? 'w-5 bg-emerald-500' : 'w-1.5 bg-muted-foreground/30'
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={prev} disabled={isFirstStep}>
              <ChevronLeft className="size-4" />
              Back
            </Button>
            <Button size="sm" onClick={next}>
              {isLastStep ? 'Finish' : 'Next'}
              {!isLastStep && <ChevronRight className="size-4" />}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
