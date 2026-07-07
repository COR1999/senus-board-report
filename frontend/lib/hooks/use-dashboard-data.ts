'use client'

import { useAsyncData, type AsyncDataState, type UseAsyncDataOptions } from './use-async-data'
import {
  getMetrics,
  getChartData,
  getReports,
  getDocuments,
  type Metrics,
  type ChartDataPoint,
  type Report,
  type DocumentItem,
} from '@/lib/data-service'

export function useMetrics(options?: UseAsyncDataOptions): AsyncDataState<Metrics> {
  return useAsyncData(getMetrics, options)
}

export function useChartData(options?: UseAsyncDataOptions): AsyncDataState<ChartDataPoint[]> {
  return useAsyncData(getChartData, options)
}

export function useReports(options?: UseAsyncDataOptions): AsyncDataState<Report[]> {
  return useAsyncData(getReports, options)
}

export function useDocuments(options?: UseAsyncDataOptions): AsyncDataState<DocumentItem[]> {
  return useAsyncData(getDocuments, options)
}
