// lib/data-service.ts
import { mockMetrics, mockChartData, mockReports } from '@/lib/mock-data'
import { FALLBACK_INSIGHTS, type Insight } from '@/lib/insights'

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

/**
 * Shared JSON fetch + error-shape helper for the backend API. Throws a
 * consistent `Error` on a non-2xx response instead of each call site
 * re-deriving its own message from `res.statusText`. Callers that want the
 * "fall back to mock data on failure" behavior (the GET helpers below) still
 * do their own try/catch around this -- this helper only removes the
 * duplicated fetch/headers/ok-check boilerplate, not the fallback policy.
 */
async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })
  if (!res.ok) {
    // FastAPI's HTTPException body is `{"detail": "..."}` -- e.g. the
    // extraction-confidence gate's specific rejection message ("This
    // document scored 0% extraction confidence..."). Falling back to
    // statusText ("Unprocessable Entity") for non-JSON error bodies would
    // silently drop that detail, same reasoning as uploadPDF's own
    // detail-parsing below (this used to be a gap only that one call site
    // had fixed -- every other apiFetch caller, e.g. importExternalFiling,
    // still showed a raw "422 Unprocessable Entity" instead).
    const detail = await res
      .json()
      .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
      .catch(() => null)
    throw new Error(detail ?? `Request to ${path} failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export interface MetricValue {
  value: string
  change: number
  trend: 'up' | 'down' | 'neutral'
  /** Raw values, oldest -> newest, for sparkline rendering. `null` means that
   * document didn't report the field (missing, not zero). */
  history: (number | null)[]
}

export interface Metrics {
  revenue: MetricValue
  customers: MetricValue
  cash: MetricValue
  ebitda: MetricValue
  // Cash & Liquidity / Solvency & Leverage / Returns / Profitability --
  // see backend/docs/metrics-expansion-plan.md. Field names match the
  // backend's JSON keys exactly (snake_case) -- getMetrics() returns
  // res.json() directly with no key-mapping layer, so these must line up
  // with DashboardSummaryResponse's actual field names, not be renamed to
  // camelCase. `value` may be a field-specific missing-value sentence
  // (e.g. "EBITDA not reported in this filing" -- see metrics.py's
  // _MISSING_VALUE_MESSAGES) or, for cash_runway specifically,
  // "Cash flow +" when operations aren't burning cash (not a numeric
  // months figure).
  ebitda_margin: MetricValue
  cash_runway: MetricValue
  interest_cover: MetricValue
  roce: MetricValue
  /** Narrative-extracted (same reliability class as `customers`) -- no
   * prior-period comparative exists, so change/trend are always 0/neutral. */
  bookings: MetricValue
  /** AI-extracted free-text reporting period for the latest document (e.g.
   * "H1 2025"), and a best-effort derived prior-period label (e.g.
   * "H1 2024"). Both null when no report/summary exists yet, or the period
   * couldn't be parsed -- use a generic fallback rather than fabricating one. */
  current_period: string | null
  prior_period: string | null
  /** When the "latest" data shown above was actually extracted (ISO
   * timestamp) -- distinct from `current_period` (the filing's *reporting*
   * period, e.g. "FY2025"). Powers the dashboard's global "Data as of ..."
   * banner. Null only when there's no data at all yet. */
  data_extracted_at: string | null
  /** The document backing "latest"/current_period above -- normally the true
   * most-recently-extracted document, but reflects whichever document_id the
   * period selector anchored this response on. Used to highlight the
   * matching point on the (always-full-history) revenue trend chart, and to
   * resolve the matching `Report.id` for persisted AI Board Insights (see
   * getStoredInsights/saveInsights below). Null only in the no-data-at-all
   * empty state. */
  document_id: number | null
}

export interface ChartDataPoint {
  /** Display label for the period, e.g. "Dec 2025". Not guaranteed monthly --
   * filings may be half-yearly or irregular, so this is a label, not a fixed cadence. */
  period: string
  /** Revenue for this period. `null` means the document didn't report it (missing, not zero). */
  revenue: number | null
  /** EBITDA for this period. `null` means the document didn't report it (missing, not zero). */
  ebitda: number | null
  /** Cash for this period. `null` means the document didn't report it (missing, not zero). */
  cash: number | null
  /** The document this point came from -- lets the chart highlight whichever
   * point matches the currently-selected period. `null` only for the single
   * synthetic prior-period point the backend may prepend when just one
   * document exists (derived from that document's own embedded prior-period
   * column, not a separate upload) -- never matches a real selection. */
  document_id: number | null
  /** This point's reporting cadence in months (6 half-year, 12 full-year),
   * when derivable -- used to split the chart into separate half-year/
   * full-year lines rather than connecting incomparable period lengths on
   * one line. `null` when undeterminable -- rendered as an isolated point. */
  cadence_months: number | null
}

export interface ReportSummary {
  company_name: string | null
  reporting_period: string | null
}

export interface Report {
  id: number
  document_id: number
  /** Null until the report finishes generating (pending/generating/failed reports may have no summary yet). */
  summary: ReportSummary | null
  status: 'pending' | 'generating' | 'completed' | 'failed'
  created_at: string
}

export type ExtractedPdfData = Record<string, unknown>

/**
 * `documentId` anchors the dashboard on a specific reporting period (see
 * the period selector, `getDashboardPeriods` below) instead of the true
 * latest -- omitted/null means "latest", today's exact default behavior.
 */
export async function getMetrics(documentId?: number | null): Promise<Metrics> {
  try {
    const query = documentId != null ? `?document_id=${documentId}` : ''
    return await apiFetch<Metrics>(`/metrics/dashboard/summary${query}`)
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock metrics:', error)
    return mockMetrics
  }
}

/**
 * Always the full revenue-trend history, regardless of which period is
 * selected elsewhere on the dashboard -- unlike `getMetrics`, this
 * deliberately takes no `documentId` param. The chart's job is showing
 * where the selected period sits in the company's whole history, which
 * needs the whole history every time; the caller highlights the selected
 * point client-side using each point's own `document_id` instead.
 */
export async function getChartData(): Promise<ChartDataPoint[]> {
  try {
    return await apiFetch<ChartDataPoint[]>('/metrics/dashboard/revenue-trend')
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock chart data:', error)
    return mockChartData
  }
}

export interface DashboardPeriod {
  document_id: number
  /** Combined bare period + calendar range, e.g. "HY2026 (Jul 2025 – Dec 2025)". */
  label: string
}

/**
 * Reporting periods available for the dashboard's period selector -- only
 * periods eligible to ever be "latest" (see backend's _HAS_CORE_METRICS/
 * _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD), newest first. Same empty-list-on-
 * failure fallback as getAvailableExternalFilings -- an unreachable backend
 * should just mean no selector renders, not break the dashboard.
 */
export async function getDashboardPeriods(): Promise<DashboardPeriod[]> {
  try {
    return await apiFetch<DashboardPeriod[]>('/metrics/dashboard/periods')
  } catch (error) {
    console.warn('Failed to fetch dashboard periods:', error)
    return []
  }
}

/**
 * AI-generated board commentary from the current KPIs, via our own
 * /api/insights Next.js route (not the Python backend -- Gemini is called
 * server-side there, keeping GEMINI_INSIGHTS_API_KEY out of the client bundle).
 */
export interface AiInsightsResult {
  insights: Insight[]
  /** True when `insights` is the static FALLBACK_INSIGHTS content, not a
   * real Gemini generation (quota exhausted, no API key, or a network/parse
   * failure). Callers must not treat this the same as a successful
   * generation -- see insights-cache.ts, which previously cached and gated
   * the manual refresh button on fallback content exactly like real
   * insights, silently blocking a retry even though nothing real had ever
   * been generated for that data. */
  isFallback: boolean
  /** The Gemini model that produced `insights`, e.g. "gemini-flash-latest" --
   * `null` for fallback content. Persisted alongside a real result via
   * `saveInsights` so a stored row records what actually generated it. */
  model: string | null
}

export async function getAiInsights(metrics: Metrics): Promise<AiInsightsResult> {
  try {
    const res = await fetch('/api/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metrics }),
    })
    if (!res.ok) throw new Error(`Failed to fetch insights: ${res.statusText}`)
    const data = await res.json()
    return { insights: data.insights, isFallback: Boolean(data.isFallback), model: data.model ?? null }
  } catch (error) {
    console.warn('Failed to fetch AI insights, using fallback:', error)
    return { insights: FALLBACK_INSIGHTS, isFallback: true, model: null }
  }
}

/**
 * Server-persisted AI Board Insights for one report -- see
 * backend/app/models/report_insights.py. This is the durable source of
 * truth `ai-insights.tsx` checks *before* ever calling Gemini: a report
 * that already has a stored result never triggers a second live generation,
 * even across a hard reload, a different browser, or a redeploy (unlike the
 * old localStorage-only cache).
 */
export interface StoredInsights {
  report_id: number
  insights: Insight[]
  model_version: string | null
  generated_at: string
}

/**
 * Resolves to `null` on a 404 ("never generated for this report yet") --
 * an expected absence, not an error, so callers can treat it as the signal
 * to fall back to a live Gemini generation rather than throwing. Still
 * throws on a genuine failure (backend unreachable, 5xx), same convention
 * as every other mutation-adjacent call in this file.
 */
export async function getStoredInsights(reportId: number): Promise<StoredInsights | null> {
  const res = await fetch(`${API_URL}/api/reports/${reportId}/insights`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (res.status === 404) return null
  if (!res.ok) {
    const detail = await res
      .json()
      .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
      .catch(() => null)
    throw new Error(detail ?? `Failed to fetch stored insights: ${res.statusText}`)
  }
  return res.json()
}

export async function saveInsights(
  reportId: number,
  insights: Insight[],
  modelVersion: string | null
): Promise<StoredInsights> {
  return apiFetch<StoredInsights>(`/api/reports/${reportId}/insights`, {
    method: 'PUT',
    body: JSON.stringify({ insights, model_version: modelVersion }),
  })
}

export async function getReports(): Promise<Report[]> {
  try {
    return await apiFetch<Report[]>('/api/reports')
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock reports:', error)
    return mockReports
  }
}

/**
 * See app/services/extraction_confidence.py. `'needs_review'` (85-94%
 * extraction confidence) shows a "Pending Review" tag -- that data is real
 * and persisted, but deliberately excluded from the dashboard's headline
 * KPIs until it clears the 95% auto-accept threshold. `'rejected'` (<85%)
 * is also persisted (reviewable, but can never reach the dashboard, and
 * has no approve path -- see the backend's `approve_document`). `null`
 * covers both "not yet scored" (no report generated) and "auto_accept"
 * (>=95%) -- no tag needed for either, so the two are never distinguished
 * on the list view.
 */
export type ExtractionConfidenceTier = 'needs_review' | 'rejected' | 'auto_accept' | null

export interface DocumentItem {
  id: number
  filename: string
  file_size: number | null
  status: string
  created_at: string
  extraction_confidence_tier: ExtractionConfidenceTier
  /** Set when this document's data has been merged into a new combined
   * document covering the same reporting period (see the backend's
   * period_merge_service.py) -- shows a "Merged" tag instead of/alongside
   * the tier tag, since a superseded document's own tier is otherwise
   * unchanged (e.g. still literally "auto_accept") despite no longer
   * driving the dashboard. `null` for the overwhelming majority of
   * documents, which aren't superseded by anything. */
  superseded_by_document_id: number | null
}

export async function getDocuments(): Promise<DocumentItem[]> {
  try {
    return await apiFetch<DocumentItem[]>('/api/documents')
  } catch (error) {
    console.warn('Failed to fetch documents:', error)
    return []
  }
}

export interface DocumentFinancialMetrics {
  revenue: number | null
  customers: number | null
  cash: number | null
  ebitda: number | null
  gross_margin: number | null
  operating_margin: number | null
  extraction_confidence: number | null
  extraction_confidence_tier: ExtractionConfidenceTier
  /** The confidence score's own human-readable point breakdown (e.g.
   * "Revenue not found (0/30)."), shown in the review panel so a rejected
   * or pending-review document's "why" is visible, not just its raw
   * values. `null` for any row scored before this field existed. */
  extraction_confidence_reasons: string[] | null
}

export interface DocumentDetail extends DocumentItem {
  financial_metrics: DocumentFinancialMetrics | null
}

/**
 * Full document detail, including the extracted financial values -- powers
 * the "Review" panel for a `needs_review` document (see approveDocument
 * below). Throws on failure rather than falling back, unlike getDocuments:
 * the review panel has nothing sensible to show for a document it can't
 * actually fetch, so the caller needs to know it failed.
 */
export async function getDocument(documentId: number): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/api/documents/${documentId}`)
}

/**
 * Confirms a human has reviewed a `needs_review` document's extracted
 * values and they're correct -- promotes it to dashboard-eligible without
 * rewriting its underlying extraction_confidence/tier (see the backend's
 * FinancialMetrics.human_approved_at docstring). Throws on failure (same
 * reasoning as deleteDocument/importExternalFiling).
 */
export async function approveDocument(documentId: number): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/api/documents/${documentId}/approve`, { method: 'POST' })
}

/**
 * URL for the original uploaded PDF -- used internally by `downloadDocument`
 * below, and by anything that just wants to link to/embed the file directly
 * (e.g. "View source" links, which don't need error handling since a 404
 * there just opens a browser error page the user already understands as
 * "this didn't work").
 */
export function getDocumentFileUrl(documentId: number): string {
  return `${API_URL}/api/documents/${documentId}/file`
}

/**
 * Downloads the original uploaded PDF as a real file-save, with a proper
 * error surfaced to the caller on failure. Deliberately a `fetch`-and-blob
 * flow, not a plain `<a href download>` navigation (this function's only
 * caller used to be exactly that) -- a plain navigation gives the browser
 * nothing to show the user when the backend 404s (Railway's filesystem
 * isn't persistent yet, see backend/README.md -- an upload from before the
 * most recent redeploy has a real, specific "no longer available" message
 * the old approach silently dropped, leaving what looked like a dead
 * button). Throws on failure so the caller can show that real message,
 * same reasoning as `deleteDocument`/`uploadPDF`.
 */
export async function downloadDocument(documentId: number, filename: string): Promise<void> {
  const res = await fetch(getDocumentFileUrl(documentId))
  if (!res.ok) {
    const detail = await res
      .json()
      .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
      .catch(() => null)
    throw new Error(detail ?? `Failed to download file: ${res.statusText}`)
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = window.document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.click()
  URL.revokeObjectURL(objectUrl)
}

/**
 * Deletes a document (and, via backend cascade, its FinancialMetrics,
 * BalanceSheetMetrics, and Report rows). Throws on failure -- unlike the
 * GET helpers above, a delete failing silently would be misleading to the
 * caller, so this is intentionally not caught-and-defaulted.
 */
export async function deleteDocument(documentId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${documentId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete document: ${res.statusText}`)
}

/** Force-regenerates a report from its source document. Throws on failure (same reasoning as deleteDocument). */
export async function regenerateReport(reportId: number): Promise<Report> {
  return apiFetch<Report>(`/api/reports/${reportId}/regenerate`, { method: 'POST' })
}

export async function uploadPDF(file: File): Promise<{ id: string; message: string }> {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch(`${API_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) {
      // FastAPI's HTTPException body is `{"detail": "..."}` -- e.g. the
      // duplicate-upload 409's specific message ("already uploaded as
      // document #3 on 2026-07-06"). Falling back to statusText ("Conflict")
      // for non-JSON error bodies would silently drop that detail.
      const detail = await res
        .json()
        .then((body) => (typeof body?.detail === 'string' ? body.detail : null))
        .catch(() => null)
      throw new Error(detail ?? `Failed to upload PDF: ${res.statusText}`)
    }
    return res.json()
  } catch (error) {
    console.error('PDF upload failed:', error)
    throw error
  }
}

export async function extractFromPDF(documentId: string): Promise<ExtractedPdfData> {
  try {
    return await apiFetch<ExtractedPdfData>(`/api/documents/${documentId}`)
  } catch (error) {
    console.error('PDF extraction failed:', error)
    throw error
  }
}

export interface ExternalFiling {
  attachment_id: string
  file_name: string
  file_size: number | null
  published_date: string | null
}

/**
 * Filings on Senus's own investor relations API not yet imported into this
 * system (see the root README's "Investor relations API" section). Checked
 * on page load / a manual "Check now" button, not polled in the background --
 * fails silently to an empty list like the other GET helpers, since an
 * unreachable IR API should just mean the banner doesn't show, not break the
 * documents page.
 */
export async function getAvailableExternalFilings(): Promise<ExternalFiling[]> {
  try {
    return await apiFetch<ExternalFiling[]>('/api/documents/external/available')
  } catch (error) {
    console.warn('Failed to check investor relations API for new filings:', error)
    return []
  }
}

/**
 * Downloads and ingests one filing from the investor relations API by its
 * attachment_id -- the same extraction/report-generation pipeline as a
 * manual upload. Throws on failure (same reasoning as uploadPDF/deleteDocument).
 */
export async function importExternalFiling(attachmentId: string): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(`/api/documents/external/${attachmentId}/import`, { method: 'POST' })
}

/**
 * Filings explicitly marked out of scope (see hideExternalFiling below) --
 * a secondary list so a dismissed non-financial filing (an AGM notice,
 * Memo & Articles) can still be reviewed/restored later, not just gone for
 * good. Same empty-list-on-failure fallback as getAvailableExternalFilings.
 */
export async function getHiddenExternalFilings(): Promise<ExternalFiling[]> {
  try {
    return await apiFetch<ExternalFiling[]>('/api/documents/external/hidden')
  } catch (error) {
    console.warn('Failed to fetch hidden filings:', error)
    return []
  }
}

/**
 * Marks a filing as out of scope so it stops showing up in the "available"
 * list -- for a filing with no extractable financial data (a governance
 * document, or one that failed the confidence gate) that the user has
 * already reviewed and doesn't want cluttering the space. Throws on
 * failure (same reasoning as deleteDocument/importExternalFiling).
 */
export async function hideExternalFiling(attachmentId: string): Promise<void> {
  await apiFetch(`/api/documents/external/${attachmentId}/hide`, { method: 'POST' })
}

/**
 * Restores a hidden filing back to the "available" list. Not routed through
 * apiFetch -- the backend returns a bodyless 204, and apiFetch's `res.json()`
 * would throw on the empty body (same reasoning as deleteDocument below,
 * which has the same 204-response shape).
 */
export async function unhideExternalFiling(attachmentId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/external/${attachmentId}/unhide`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to unhide filing: ${res.statusText}`)
}