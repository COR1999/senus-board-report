import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PresentationProvider, usePresentation } from '@/components/presentation/presentation-context'
import { PresentationOverlay } from '@/components/presentation/presentation-overlay'
import type { PresentationStep } from '@/lib/presentation/steps'
import * as dataService from '@/lib/data-service'

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}))

const TEST_STEPS: PresentationStep[] = [
  { id: 'step-a', page: '/', title: 'Step A', subtitle: 'a subtitle', talkingPoint: 'ask a' },
  {
    id: 'step-b',
    page: '/',
    title: 'Step B',
    subtitle: 'b subtitle',
    talkingPoint: 'ask b',
    demoUploads: [{ fileName: 'demo-filing.pdf', publicPath: '/demo-documents/demo-filing.pdf' }],
  },
]

// Auto-starts the tour on mount so each test doesn't need its own "click
// start" button -- the overlay itself has no start control (that's
// PresentationTrigger's job, tested separately).
function AutoStart() {
  const { start } = usePresentation()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- runs exactly
  // once, on mount; `start` is stable within a single test render.
  useEffect(() => {
    start()
  }, [])
  return null
}

function renderActive(steps: PresentationStep[] = TEST_STEPS) {
  return render(
    <PresentationProvider allSteps={steps}>
      <div id="step-a">A content</div>
      <div id="step-b">B content</div>
      <AutoStart />
      <PresentationOverlay />
    </PresentationProvider>
  )
}

describe('PresentationOverlay', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('renders nothing before the tour starts', () => {
    render(
      <PresentationProvider allSteps={TEST_STEPS}>
        <div id="step-a">A content</div>
        <div id="step-b">B content</div>
        <PresentationOverlay />
      </PresentationProvider>
    )

    expect(screen.queryByRole('dialog', { name: /presentation mode/i })).not.toBeInTheDocument()
  })

  it('shows the current step title, subtitle, talking point, and progress once active', async () => {
    renderActive()

    expect(await screen.findByRole('dialog', { name: /presentation mode/i })).toBeInTheDocument()
    expect(screen.getByText('Step A')).toBeInTheDocument()
    expect(screen.getByText('a subtitle')).toBeInTheDocument()
    expect(screen.getByText('ask a')).toBeInTheDocument()
    expect(screen.getByText(/presenting.*1\s*\/\s*2/i)).toBeInTheDocument()
  })

  it('disables Back on the first step and shows Finish on the last', async () => {
    renderActive()
    await screen.findByText('Step A')

    expect(screen.getByRole('button', { name: /back/i })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: /^next$/i }))

    await screen.findByText('Step B')
    // Step B has a demoUpload that resolves quickly (mocked below via a
    // rejected fetch, which still clears processingLabel) -- wait for the
    // footer (and its Finish label) to reappear.
    await waitFor(() => expect(screen.getByRole('button', { name: /finish/i })).toBeInTheDocument())
  })

  it('clicking Exit stops the presentation', async () => {
    renderActive()
    await screen.findByText('Step A')

    fireEvent.click(screen.getByRole('button', { name: /exit presentation/i }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: /presentation mode/i })).not.toBeInTheDocument())
  })

  it('shows a processing state instead of the footer while a demo upload is in flight', async () => {
    let resolveUpload: (value: { id: string; message: string }) => void = () => {}
    const uploadPromise = new Promise<{ id: string; message: string }>((resolve) => {
      resolveUpload = resolve
    })
    vi.spyOn(dataService, 'uploadPDF').mockReturnValue(uploadPromise)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }) })
    )

    renderActive()
    await screen.findByText('Step A')
    fireEvent.click(screen.getByRole('button', { name: /^next$/i }))

    expect(await screen.findByText(/uploading demo-filing\.pdf/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^next$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()

    resolveUpload({ id: '1', message: 'ok' })
    await waitFor(() => expect(screen.queryByText(/uploading demo-filing\.pdf/i)).not.toBeInTheDocument())
  })
})
