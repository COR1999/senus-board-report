'use client'

import { useAsyncData, type AsyncDataState } from './use-async-data'
import {
  getMetrics,
  getChartData,
  getSegmentBreakdown,
  getReports,
  getDocuments,
  type Metrics,
  type ChartDataPoint,
  type SegmentValue,
  type Report,
  type DocumentItem,
} from '@/lib/data-service'

export function useMetrics(): AsyncDataState<Metrics> {
  return useAsyncData(getMetrics)
}

export function useChartData(): AsyncDataState<ChartDataPoint[]> {
  return useAsyncData(getChartData)
}

export function useSegments(): AsyncDataState<SegmentValue[]> {
  return useAsyncData(getSegmentBreakdown)
}

export function useReports(): AsyncDataState<Report[]> {
  return useAsyncData(getReports)
}

export function useDocuments(): AsyncDataState<DocumentItem[]> {
  return useAsyncData(getDocuments)
}
