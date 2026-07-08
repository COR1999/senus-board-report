'use client'

import { useAsyncData, type AsyncDataState, type UseAsyncDataOptions } from './use-async-data'
import {
  getMetrics,
  getChartData,
  getReports,
  getDocuments,
  getAvailableExternalFilings,
  getDashboardPeriods,
  type Metrics,
  type ChartDataPoint,
  type Report,
  type DocumentItem,
  type ExternalFiling,
  type DashboardPeriod,
} from '@/lib/data-service'

/**
 * `documentId` anchors both hooks on a specific reporting period (see the
 * period selector) instead of the true latest -- `null` means "latest".
 * Added to `useAsyncData`'s `deps` so switching periods triggers a refetch.
 */
export function useMetrics(documentId: number | null, options?: UseAsyncDataOptions): AsyncDataState<Metrics> {
  return useAsyncData(() => getMetrics(documentId), {
    ...options,
    deps: [documentId, ...(options?.deps ?? [])],
  })
}

export function useChartData(documentId: number | null, options?: UseAsyncDataOptions): AsyncDataState<ChartDataPoint[]> {
  return useAsyncData(() => getChartData(documentId), {
    ...options,
    deps: [documentId, ...(options?.deps ?? [])],
  })
}

// No `pollIntervalMs` -- the period list rarely changes within a session
// (only after a new document is imported/generated elsewhere), and the
// dashboard container's own metrics/chart polling already refreshes what's
// shown for whichever period is selected.
export function usePeriods(options?: UseAsyncDataOptions): AsyncDataState<DashboardPeriod[]> {
  return useAsyncData(getDashboardPeriods, options)
}

export function useReports(options?: UseAsyncDataOptions): AsyncDataState<Report[]> {
  return useAsyncData(getReports, options)
}

export function useDocuments(options?: UseAsyncDataOptions): AsyncDataState<DocumentItem[]> {
  return useAsyncData(getDocuments, options)
}

// No `pollIntervalMs` -- checked on page load and via a manual "Check now"
// button (`refetch`), not a background poller, per product direction.
export function useAvailableExternalFilings(options?: UseAsyncDataOptions): AsyncDataState<ExternalFiling[]> {
  return useAsyncData(getAvailableExternalFilings, options)
}
