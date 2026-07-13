/**
 * Ordered step config for Presentation Mode -- a guided, boardroom-style
 * walkthrough of the live app (see components/presentation/). Spans three
 * routes on purpose: the extraction/confidence pipeline (this project's
 * most distinctive piece of engineering -- automatic confidence scoring,
 * auto-accept/needs-review/rejected tiers, human-approval workflow) only
 * has a real UI on /documents, not on the executive dashboard itself.
 *
 * Not every step is present on every visit -- `growth-forecast` only
 * renders when there's a real revenue baseline to project from (see
 * dashboard-container.tsx). PresentationProvider filters this list down to
 * steps whose target element actually exists in the DOM before starting,
 * so the tour never stalls on a missing slide.
 *
 * Deliberately does NOT open on an empty dashboard or the frontend's
 * static mock-data fallback -- backend/scripts/local_demo_seed.py
 * pre-seeds one real, reliably-extracted filing (the HY2026 half-year PR)
 * before Presentation Mode ever starts, specifically so every slide shows
 * real, complete data from the first click, including a real Cost
 * Waterfall (that filing discloses a full P&L breakdown). The documents
 * step below then live-uploads two MORE filings that merge into a second,
 * brand new period -- additive to that baseline, never load-bearing for
 * it.
 */
/** A demo document uploaded live, on entering a step, through the real
 * upload endpoint -- see presentation-context.tsx's `runDemoUploads`. */
export interface DemoUpload {
  /** Filename as it should be stored/displayed server-side (matches the
   * real filing's own name, so the table row reads exactly like a genuine
   * upload). */
  fileName: string
  /** Path under /public the bytes are fetched from client-side before
   * being re-posted as multipart form data. */
  publicPath: string
}

/** Dispatched on `window` after each live demo upload completes (success
 * or failure) -- listened for by /documents (see app/documents/page.tsx)
 * to refetch its own document list, since PresentationProvider triggering
 * the upload has no direct handle on that page's local state. A plain
 * DOM event is simpler and more decoupled here than threading a refetch
 * callback through global presentation state that only one page cares
 * about. */
export const PRESENTATION_DOCUMENTS_CHANGED_EVENT = 'presentation:documents-changed'

export interface PresentationStep {
  id: string
  page: string
  title: string
  subtitle: string
  /** A short discussion question, grounded in a real design decision or
   * bug fix from this project rather than a generic "any questions?"
   * prompt -- kept to one short sentence, no "Ask me:" framing (the icon
   * next to it already signals what it is; spelling that out read as
   * pushy, per direct feedback). The point is to open a conversation, not
   * quiz the audience. */
  talkingPoint: string
  /** Uploaded, in order, the first time this step is entered -- never
   * repeated on a later revisit (see the `uploadedFileNames` guard in
   * presentation-context.tsx), so stepping Back and Next again doesn't
   * attempt a duplicate upload. */
  demoUploads?: DemoUpload[]
}

export const PRESENTATION_STEPS: PresentationStep[] = [
  {
    id: 'presentation-step-hero',
    page: '/',
    title: 'Headline KPIs',
    subtitle: 'Revenue, EBITDA, cash and customers — the numbers a board checks first.',
    talkingPoint: 'A missing figure is never shown as €0.',
  },
  {
    id: 'presentation-step-revenue-trend',
    page: '/',
    title: 'Revenue Trend',
    subtitle: 'Trend across every period on file, with forecasting once there’s enough history.',
    talkingPoint: 'How does it choose between a stat, a bar, and a line?',
  },
  {
    id: 'presentation-step-cost-waterfall',
    page: '/',
    title: 'Cost Waterfall',
    subtitle: 'Revenue broken down step-by-step into EBITDA.',
    talkingPoint: 'What if a filing skips the cost breakdown?',
  },
  {
    id: 'presentation-step-financial-health',
    page: '/',
    title: 'Financial Health',
    subtitle: 'Growth, profitability, cash, solvency, returns — five required categories.',
    talkingPoint: 'How does it pick which ratio to show?',
  },
  {
    id: 'presentation-step-growth-forecast',
    page: '/',
    title: 'Growth to 2030',
    subtitle: "Progress against Senus's own published 50% CAGR target.",
    talkingPoint: 'Trend line, or something else?',
  },
  {
    id: 'presentation-step-ai-insights',
    page: '/',
    title: 'AI Board Insights',
    subtitle: 'AI commentary on this period, and the trend across every filing.',
    talkingPoint: 'What happens if the AI quota runs out?',
  },
  {
    id: 'presentation-step-recent-reports',
    page: '/',
    title: 'Recent Reports',
    subtitle: 'Every filing behind these numbers, one click away.',
    talkingPoint: 'What happens end to end on upload?',
  },
  {
    id: 'presentation-step-documents-table',
    page: '/documents',
    title: 'Extraction & Confidence Pipeline',
    subtitle:
      'Every upload is scored for confidence — auto-accepted, flagged for review, or rejected. These two live uploads share the same FY2025 period, so watch them merge.',
    talkingPoint: 'What if two filings disagree on a figure?',
    demoUploads: [
      { fileName: 'ADF_Farm_Solutions_Financial_Statements_Jun2025.pdf', publicPath: '/demo-documents/ADF_Farm_Solutions_Financial_Statements_Jun2025.pdf' },
      { fileName: 'Senus PLC Information Document December 2025.pdf', publicPath: '/demo-documents/Senus_PLC_Information_Document_Dec2025.pdf' },
    ],
  },
  {
    id: 'presentation-step-reports-archive',
    page: '/reports',
    title: 'Reports Archive',
    subtitle: 'Every board report generated from an uploaded filing.',
    talkingPoint: 'How does it avoid AI-hallucinated numbers?',
  },
  {
    id: 'presentation-step-revenue-trend',
    page: '/',
    title: 'Revenue Trend — Live Payoff',
    subtitle: 'The FY2025 period just merged now sits alongside the half-year baseline.',
    talkingPoint: 'Why keep half-year and full-year on separate lines?',
  },
]
