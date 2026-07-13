'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import {
  PRESENTATION_STEPS,
  PRESENTATION_DOCUMENTS_CHANGED_EVENT,
  type PresentationStep,
  type DemoUpload,
} from '@/lib/presentation/steps'
import { uploadPDF } from '@/lib/data-service'

interface PresentationContextValue {
  active: boolean
  currentStep: PresentationStep | null
  stepNumber: number
  totalSteps: number
  isFirstStep: boolean
  isLastStep: boolean
  /** Non-null while a step's demoUploads are in flight -- the label to
   * show in place of the normal Back/Next controls (see
   * PresentationOverlay). */
  processingLabel: string | null
  start: () => void
  stop: () => void
  next: () => void
  prev: () => void
}

const PresentationContext = createContext<PresentationContextValue | null>(null)

// Tailwind class *names*, not computed strings -- classList.add/remove
// needs the literal classes to already exist in the compiled CSS, which
// only happens because these exact strings appear here as source text for
// Tailwind's scanner to find.
// ring-offset-2 (not -4/-8) deliberately -- dashboard sections are only
// space-y-6 (24px) apart, so a wider offset risks the ring bleeding into
// the *next* card's own top edge/labels rather than just framing the
// highlighted one.
const HIGHLIGHT_CLASSES = ['ring-2', 'ring-emerald-500', 'ring-offset-2', 'ring-offset-background', 'rounded-2xl']

const MAX_ELEMENT_WAIT_MS = 4000
const ELEMENT_POLL_INTERVAL_MS = 100

/**
 * Polls for a section's target element rather than assuming it's already
 * mounted -- a cross-page step needs a client-side navigation to land
 * first, and even a same-page step can be one whose data is still loading
 * (dashboard sections render nothing until their own fetch resolves).
 * Resolves `null` (not a rejection) on timeout so a genuinely-absent
 * conditional section (e.g. no cost waterfall for this filing) degrades to
 * "no highlight" instead of breaking the tour.
 */
function waitForElement(id: string, timeoutMs: number): Promise<HTMLElement | null> {
  return new Promise((resolve) => {
    const existing = document.getElementById(id)
    if (existing) {
      resolve(existing)
      return
    }
    const startedAt = Date.now()
    const interval = setInterval(() => {
      const el = document.getElementById(id)
      if (el) {
        clearInterval(interval)
        resolve(el)
      } else if (Date.now() - startedAt > timeoutMs) {
        clearInterval(interval)
        resolve(null)
      }
    }, ELEMENT_POLL_INTERVAL_MS)
  })
}

/** Fetches a bundled /public PDF and re-wraps it as a File with the real
 * filing's own name, so the upload endpoint (and the resulting table row)
 * behaves identically to a human picking the same file from disk. */
async function fetchDemoFile(upload: DemoUpload): Promise<File> {
  const res = await fetch(upload.publicPath)
  if (!res.ok) throw new Error(`Could not load demo asset ${upload.publicPath}: ${res.statusText}`)
  const blob = await res.blob()
  return new File([blob], upload.fileName, { type: 'application/pdf' })
}

/**
 * Global, cross-page "Present" mode -- a guided, live-data walkthrough of
 * the app for a boardroom demo (see lib/presentation/steps.ts for the step
 * list and why it spans three routes). Mounted once in app/layout.tsx so
 * its state survives client-side navigation between pages (the root layout
 * itself never unmounts on route change, which is what makes this work
 * without sessionStorage/query-param plumbing).
 *
 * The "Present" trigger only ever lives on the dashboard page ("/", the
 * tour's first step), which is what makes `start()`'s existence filter
 * below safe: it only checks conditional sections (cost waterfall, growth
 * forecast) against the DOM for steps on the CURRENT page, trusting
 * steps on other pages to exist once navigated to (true for every
 * documents/reports step -- none of those sections are conditional).
 */
export function PresentationProvider({
  children,
  allSteps = PRESENTATION_STEPS,
}: {
  children: React.ReactNode
  /** Defaults to the real app-wide step list; overridable only so tests
   * can exercise this provider's navigation/upload logic against a small,
   * self-contained step list instead of the full real one. */
  allSteps?: PresentationStep[]
}) {
  const router = useRouter()
  const pathname = usePathname()
  const [active, setActive] = useState(false)
  const [steps, setSteps] = useState<PresentationStep[]>([])
  const [stepIndex, setStepIndex] = useState(0)
  const [processingLabel, setProcessingLabel] = useState<string | null>(null)
  const highlightedRef = useRef<HTMLElement | null>(null)
  // Filenames already uploaded (or already attempted and failed) this
  // presentation run -- stepping Back then Next past the same
  // demoUploads step again must not re-upload (the backend would 409 on
  // the exact-duplicate content anyway, but silently skipping is better
  // live-demo behavior than surfacing that as an error a second time).
  const uploadedFileNamesRef = useRef<Set<string>>(new Set())

  const clearHighlight = useCallback(() => {
    if (highlightedRef.current) {
      highlightedRef.current.classList.remove(...HIGHLIGHT_CLASSES)
      highlightedRef.current = null
    }
  }, [])

  const runDemoUploads = useCallback(async (uploads: DemoUpload[] | undefined) => {
    if (!uploads || uploads.length === 0) return
    for (const upload of uploads) {
      if (uploadedFileNamesRef.current.has(upload.fileName)) continue
      setProcessingLabel(`Uploading ${upload.fileName}…`)
      try {
        const file = await fetchDemoFile(upload)
        await uploadPDF(file)
      } catch (error) {
        // A live demo shouldn't hard-stop on an upload hiccup -- log it and
        // let the presenter keep going; that one row just won't appear.
        console.warn(`Presentation Mode: demo upload of "${upload.fileName}" failed`, error)
      } finally {
        uploadedFileNamesRef.current.add(upload.fileName)
      }
    }
    setProcessingLabel(null)
    window.dispatchEvent(new CustomEvent(PRESENTATION_DOCUMENTS_CHANGED_EVENT))
  }, [])

  const start = useCallback(() => {
    const initial = allSteps.filter(
      (step) => step.page !== pathname || document.getElementById(step.id) !== null
    )
    if (initial.length === 0) return
    setSteps(initial)
    setStepIndex(0)
    setActive(true)
  }, [pathname, allSteps])

  const stop = useCallback(() => {
    clearHighlight()
    setActive(false)
  }, [clearHighlight])

  const goToIndex = useCallback(
    async (index: number, currentSteps: PresentationStep[]) => {
      if (index < 0 || index >= currentSteps.length) return
      const step = currentSteps[index]
      setStepIndex(index)
      clearHighlight()
      if (pathname !== step.page) {
        router.push(step.page)
      }
      const el = await waitForElement(step.id, MAX_ELEMENT_WAIT_MS)
      if (el) {
        el.classList.add(...HIGHLIGHT_CLASSES)
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        highlightedRef.current = el
      }
      // Runs after the highlight/scroll so the presenter sees the target
      // section first, then watches the new row/data appear live -- not
      // uploaded silently before the audience can even see where it lands.
      await runDemoUploads(step.demoUploads)
    },
    [pathname, router, clearHighlight, runDemoUploads]
  )

  const next = useCallback(() => {
    if (processingLabel) return // a demo upload is already in flight -- ignore a double Next/Space
    if (stepIndex >= steps.length - 1) {
      stop()
      return
    }
    goToIndex(stepIndex + 1, steps)
  }, [processingLabel, stepIndex, steps, goToIndex, stop])

  const prev = useCallback(() => {
    if (processingLabel) return
    goToIndex(Math.max(0, stepIndex - 1), steps)
  }, [processingLabel, stepIndex, steps, goToIndex])

  // Performs the very first highlight once `start()` has populated `steps`
  // and flipped `active` -- kept as its own effect (rather than done inline
  // in `start()`) so it shares the exact same navigate-and-highlight path
  // as next()/prev() instead of a third, duplicated implementation.
  useEffect(() => {
    if (active && steps.length > 0 && stepIndex === 0) {
      goToIndex(0, steps)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fires once per fresh `start()` (active flips true alongside a new `steps` array), not on every goToIndex/stepIndex change.
  }, [active, steps])

  useEffect(() => {
    if (!active) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        next()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        prev()
      } else if (e.key === 'Escape') {
        stop()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [active, next, prev, stop])

  // Belt-and-braces: clear a stale highlight ring if this provider itself
  // ever unmounts mid-presentation (it won't in practice -- it's mounted
  // once at the root layout -- but a highlighted element should never be
  // able to outlive the mode that applied it).
  useEffect(() => () => clearHighlight(), [clearHighlight])

  const currentStep = steps[stepIndex] ?? null

  const value = useMemo<PresentationContextValue>(
    () => ({
      active,
      currentStep,
      stepNumber: stepIndex + 1,
      totalSteps: steps.length,
      isFirstStep: stepIndex === 0,
      isLastStep: stepIndex === steps.length - 1,
      processingLabel,
      start,
      stop,
      next,
      prev,
    }),
    [active, currentStep, stepIndex, steps.length, processingLabel, start, stop, next, prev]
  )

  return <PresentationContext.Provider value={value}>{children}</PresentationContext.Provider>
}

export function usePresentation(): PresentationContextValue {
  const ctx = useContext(PresentationContext)
  if (!ctx) throw new Error('usePresentation must be used within a PresentationProvider')
  return ctx
}
