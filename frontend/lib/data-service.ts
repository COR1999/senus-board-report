// lib/data-service.ts
import { mockMetrics, mockChartData, mockReports } from '@/lib/mock-data'

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export interface MetricValue {
  value: string
  change: number
  trend: 'up' | 'down'
}

export interface Metrics {
  revenue: MetricValue
  customers: MetricValue
  cash: MetricValue
  ebitda: MetricValue
}

export interface ChartDataPoint {
  month: string
  revenue: number
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

// export async function getChartData(): Promise<ChartDataPoint[]> {
//   try {
//     const res = await fetch(`${API_URL}/metrics`, {
//       method: 'GET',
//       headers: {
//         'Content-Type': 'application/json',
//       },
//     })
//     if (!res.ok) throw new Error(`Failed to fetch chart data: ${res.statusText}`)
//     const data = await res.json()
//     // Transform backend response to chart format if needed
//     return mockChartData // TODO: Transform actual data from backend
//   } catch (error) {
//     console.warn('Failed to fetch chart data, using mock data:', error)
//     return mockChartData
//   }
// }
export async function getChartData(): Promise<ChartDataPoint[]> {
  try {
    // For now, return mock chart data
    // TODO: Add /api/metrics/chart endpoint to backend
    return mockChartData
  } catch (error) {
    console.warn('Using mock chart data:', error)
    return mockChartData
  }
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