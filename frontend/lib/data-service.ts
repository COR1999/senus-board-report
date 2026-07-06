// lib/data-service.ts
import { mockMetrics, mockChartData, mockReports, mockSegments } from '@/lib/mock-data'

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

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
}

export interface ChartDataPoint {
  /** Display label for the period, e.g. "Dec 2025". Not guaranteed monthly --
   * filings may be half-yearly or irregular, so this is a label, not a fixed cadence. */
  period: string
  /** Revenue for this period. `null` means the document didn't report it (missing, not zero). */
  revenue: number | null
}

export interface SegmentValue {
  segment: string
  value: number
  /** 0-100, share of total revenue this segment represents */
  percentage: number
}

export interface Report {
  id: number
  name: string
  date: string
  status: 'completed' | 'pending' | 'processing'
}

export type ExtractedPdfData = Record<string, unknown>

export async function getMetrics(): Promise<Metrics> {
  try {
    const res = await fetch(`${API_URL}/metrics/dashboard/summary`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.statusText}`)
    return res.json()
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock metrics:', error)
    return mockMetrics
  }
}

export async function getChartData(): Promise<ChartDataPoint[]> {
  try {
    const res = await fetch(`${API_URL}/metrics/dashboard/revenue-trend`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) throw new Error(`Failed to fetch chart data: ${res.statusText}`)
    return res.json()
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock chart data:', error)
    return mockChartData
  }
}

/**
 * Revenue split by customer segment (Government / Corporate / Agriculture).
 * NOTE: there is no backend extraction for this yet -- segment data isn't
 * captured anywhere in FinancialMetrics (see backend/docs/metrics-expansion-plan.md,
 * which flags similar narrative-derived breakdowns like Channels/Bookings as
 * needing separate LLM-based extraction work). This returns mock data only,
 * by design, until that backend work exists.
 */
export async function getSegmentBreakdown(): Promise<SegmentValue[]> {
  return mockSegments
}

export async function getReports(): Promise<Report[]> {
  try {
    const res = await fetch(`${API_URL}/api/reports`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) throw new Error(`Failed to fetch reports: ${res.statusText}`)
    return res.json()
  } catch (error) {
    console.warn('Failed to fetch from backend, using mock reports:', error)
    return mockReports
  }
}

export async function uploadPDF(file: File): Promise<{ id: string; message: string }> {
  try {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch(`${API_URL}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) throw new Error(`Failed to upload PDF: ${res.statusText}`)
    return res.json()
  } catch (error) {
    console.error('PDF upload failed:', error)
    throw error
  }
}

export async function extractFromPDF(documentId: string): Promise<ExtractedPdfData> {
  try {
    const res = await fetch(`${API_URL}/api/documents/${documentId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) throw new Error(`Failed to extract from PDF: ${res.statusText}`)
    return res.json()
  } catch (error) {
    console.error('PDF extraction failed:', error)
    throw error
  }
}