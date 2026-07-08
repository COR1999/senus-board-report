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
  if (!res.ok) throw new Error(`Request to ${path} failed: ${res.status} ${res.statusText}`)
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
  // camelCase. `value` may be "N/A" (no underlying data) or, for
  // cash_runway specifically, "Cash flow +" when operations aren't
  // burning cash (not a numeric months figure).
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

export async function getMetrics(): Promise<Metrics> {
  try {
    return await apiFetch<Metrics>('/metrics/dashboard/summary')
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock metrics:', error)
    return mockMetrics
  }
}

export async function getChartData(): Promise<ChartDataPoint[]> {
  try {
    return await apiFetch<ChartDataPoint[]>('/metrics/dashboard/revenue-trend')
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock chart data:', error)
    return mockChartData
  }
}

/**
 * AI-generated board commentary from the current KPIs, via our own
 * /api/insights Next.js route (not the Python backend -- Gemini is called
 * server-side there, keeping GEMINI_INSIGHTS_API_KEY out of the client bundle).
 */
export async function getAiInsights(metrics: Metrics): Promise<Insight[]> {
  try {
    const res = await fetch('/api/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metrics }),
    })
    if (!res.ok) throw new Error(`Failed to fetch insights: ${res.statusText}`)
    const data = await res.json()
    return data.insights
  } catch (error) {
    console.warn('Failed to fetch AI insights, using fallback:', error)
    return FALLBACK_INSIGHTS
  }
}

export async function getReports(): Promise<Report[]> {
  try {
    return await apiFetch<Report[]>('/api/reports')
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock reports:', error)
    return mockReports
  }
}

export interface DocumentItem {
  id: number
  filename: string
  file_size: number | null
  status: string
  created_at: string
}

export async function getDocuments(): Promise<DocumentItem[]> {
  try {
    return await apiFetch<DocumentItem[]>('/api/documents')
  } catch (error) {
    console.warn('Failed to fetch documents:', error)
    return []
  }
}

/**
 * URL for downloading the original uploaded PDF. Not a `fetch`-based
 * helper like the others -- callers plug this straight into an `<a href>`,
 * so the browser handles the download itself (no CORS concern, unlike
 * `fetch`, since it's a plain navigation/download, not a script-read
 * response). The backend may 404 with a specific "no longer available"
 * message if the file wasn't retained across a redeploy -- Railway's
 * filesystem isn't persistent yet, see backend/README.md.
 */
export function getDocumentFileUrl(documentId: number): string {
  return `${API_URL}/api/documents/${documentId}/file`
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