import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PresentationProvider, usePresentation } from '@/components/presentation/presentation-context'
import type { PresentationStep } from '@/lib/presentation/steps'
import * as dataService from '@/lib/data-service'

const pushMock = vi.fn()

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: pushMock }),
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
  { id: 'step-c', page: '/', title: 'Step C', subtitle: 'c subtitle', talkingPoint: 'ask c' },
]

// A step whose target never exists anywhere -- exercises the "genuinely
// absent conditional section" filter in `start()`.
const STEPS_WITH_MISSING: PresentationStep[] = [
  TEST_STEPS[0],
  { id: 'step-missing', page: '/', title: 'Missing', subtitle: 'never rendered', talkingPoint: 'n/a' },
  TEST_STEPS[2],
]

function Harness() {
  const { active, currentStep, stepNumber, totalSteps, isFirstStep, isLastStep, processingLabel, start, stop, next, prev } =
    usePresentation()
  return (
    <div>
      <button onClick={start}>start</button>
      <button onClick={next}>next</button>
      <button onClick={prev}>prev</button>
      <button onClick={stop}>stop</button>
      <div data-testid="active">{String(active)}</div>
      <div data-testid="title">{currentStep?.title ?? ''}</div>
      <div data-testid="step-number">{stepNumber}</div>
      <div data-testid="total-steps">{totalSteps}</div>
      <div data-testid="first">{String(isFirstStep)}</div>
      <div data-testid="last">{String(isLastStep)}</div>
      <div data-testid="processing">{processingLabel ?? ''}</div>
    </div>
  )
}

function renderWithTargets(steps: PresentationStep[]) {
  return render(
    <PresentationProvider allSteps={steps}>
      <div id="step-a">A content</div>
      <div id="step-b">B content</div>
      <div id="step-c">C content</div>
      <Harness />
    </PresentationProvider>
  )
}

describe('PresentationProvider', () => {
  beforeEach(() => {
    pushMock.mockClear()
    // jsdom doesn't implement smooth-scroll -- goToIndex calls this
    // unconditionally on every highlighted element.
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('start() activates on the first step and highlights its target element', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('true'))
    expect(screen.getByTestId('title')).toHaveTextContent('Step A')
    expect(screen.getByTestId('step-number')).toHaveTextContent('1')
    expect(screen.getByTestId('total-steps')).toHaveTextContent('3')
    expect(screen.getByTestId('first')).toHaveTextContent('true')
    await waitFor(() => expect(document.getElementById('step-a')).toHaveClass('ring-emerald-500'))
  })

  it('next() advances the step and moves the highlight, clearing it from the previous target', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))

    fireEvent.click(screen.getByText('next'))

    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step B'))
    await waitFor(() => expect(document.getElementById('step-b')).toHaveClass('ring-emerald-500'))
    expect(document.getElementById('step-a')).not.toHaveClass('ring-emerald-500')
  })

  it('prev() moves back a step', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    fireEvent.click(screen.getByText('next'))
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step B'))

    fireEvent.click(screen.getByText('prev'))

    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))
  })

  it('next() on the last step exits the presentation instead of overrunning', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    fireEvent.click(screen.getByText('next'))
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step B'))
    fireEvent.click(screen.getByText('next'))
    await waitFor(() => expect(screen.getByTestId('last')).toHaveTextContent('true'))

    fireEvent.click(screen.getByText('next'))

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('false'))
  })

  it('stop() exits and clears the highlight ring', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    await waitFor(() => expect(document.getElementById('step-a')).toHaveClass('ring-emerald-500'))

    fireEvent.click(screen.getByText('stop'))

    expect(screen.getByTestId('active')).toHaveTextContent('false')
    expect(document.getElementById('step-a')).not.toHaveClass('ring-emerald-500')
  })

  it('responds to ArrowRight/ArrowLeft/Escape keyboard shortcuts', async () => {
    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step B'))

    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))

    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('false'))
  })

  it('start() filters out a step whose target element genuinely does not exist', async () => {
    renderWithTargets(STEPS_WITH_MISSING)
    fireEvent.click(screen.getByText('start'))

    await waitFor(() => expect(screen.getByTestId('total-steps')).toHaveTextContent('2'))
    expect(screen.getByTestId('title')).toHaveTextContent('Step A')
  })

  it('uploads a demoUploads file when entering its step, showing a processing state meanwhile', async () => {
    let resolveUpload: (value: { id: string; message: string }) => void = () => {}
    const uploadPromise = new Promise<{ id: string; message: string }>((resolve) => {
      resolveUpload = resolve
    })
    const uploadSpy = vi.spyOn(dataService, 'uploadPDF').mockReturnValue(uploadPromise)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }) })
    )
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))

    fireEvent.click(screen.getByText('next'))

    await waitFor(() => expect(screen.getByTestId('processing')).toHaveTextContent('Uploading demo-filing.pdf'))
    expect(uploadSpy).toHaveBeenCalledTimes(1)
    const uploadedFile = uploadSpy.mock.calls[0][0]
    expect(uploadedFile.name).toBe('demo-filing.pdf')

    resolveUpload({ id: '1', message: 'ok' })

    await waitFor(() => expect(screen.getByTestId('processing')).toHaveTextContent(''))
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: 'presentation:documents-changed' }))
  })

  it('does not re-upload the same demoUploads file on a later revisit', async () => {
    const uploadSpy = vi.spyOn(dataService, 'uploadPDF').mockResolvedValue({ id: '1', message: 'ok' })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }) })
    )

    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    fireEvent.click(screen.getByText('next')) // -> Step B, uploads once
    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(screen.getByTestId('processing')).toHaveTextContent(''))

    fireEvent.click(screen.getByText('prev')) // -> Step A
    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step A'))
    fireEvent.click(screen.getByText('next')) // -> Step B again

    await waitFor(() => expect(screen.getByTestId('title')).toHaveTextContent('Step B'))
    expect(uploadSpy).toHaveBeenCalledTimes(1)
  })

  it('ignores Next/Prev while a demo upload is still in flight', async () => {
    let resolveUpload: (value: { id: string; message: string }) => void = () => {}
    const uploadPromise = new Promise<{ id: string; message: string }>((resolve) => {
      resolveUpload = resolve
    })
    vi.spyOn(dataService, 'uploadPDF').mockReturnValue(uploadPromise)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }) })
    )

    renderWithTargets(TEST_STEPS)
    fireEvent.click(screen.getByText('start'))
    fireEvent.click(screen.getByText('next')) // -> Step B, upload in flight
    await waitFor(() => expect(screen.getByTestId('processing')).not.toHaveTextContent(''))

    fireEvent.click(screen.getByText('next'))
    // Still on Step B, still processing -- the click above must have been a no-op.
    expect(screen.getByTestId('title')).toHaveTextContent('Step B')

    resolveUpload({ id: '1', message: 'ok' })
    await waitFor(() => expect(screen.getByTestId('processing')).toHaveTextContent(''))
  })
})
