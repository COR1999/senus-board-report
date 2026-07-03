// lib/data-service.ts
import { mockMetrics, mockChartData, mockReports } from '@/lib/mock-data'

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

export async function getMetrics(): Promise<Metrics> {
  try {
    const res = await fetch('/api/metrics')
    if (!res.ok) throw new Error('Failed to fetch metrics')
    return res.json()
  } catch (error) {
    console.warn('Using mock metrics:', error)
    return mockMetrics
  }
}

export async function getChartData(): Promise<ChartDataPoint[]> {
  try {
    const res = await fetch('/api/chart-data')
    if (!res.ok) throw new Error('Failed to fetch chart data')
    return res.json()
  } catch (error) {
    console.warn('Using mock chart data:', error)
    return mockChartData
  }
}

export async function getReports(): Promise<Report[]> {
  try {
    const res = await fetch('/api/reports')
    if (!res.ok) throw new Error('Failed to fetch reports')
    return res.json()
  } catch (error) {
    console.warn('Using mock reports:', error)
    return mockReports
  }
}