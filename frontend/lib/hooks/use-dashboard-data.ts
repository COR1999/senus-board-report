'use client'

import { useAsyncData, type AsyncDataState, type UseAsyncDataOptions } from './use-async-data'
import {
  getMetrics,
  getChartData,
  getReports,
  getDocuments,
  getDocument,
  getAvailableExternalFilings,
  getHiddenExternalFilings,
  getDashboardPeriods,
  type Metrics,
  type ChartDataPoint,
  type Report,
  type DocumentItem,
  type DocumentDetail,
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

// Deliberately no `documentId` param, unlike `useMetrics` -- the trend
// chart always shows the whole history regardless of which period is
// selected elsewhere (see `getChartData`'s own docstring), so switching
// periods never triggers a chart refetch, only a KPI refetch.
export function useChartData(options?: UseAsyncDataOptions): AsyncDataState<ChartDataPoint[]> {
  return useAsyncData(getChartData, options)
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

/**
 * Full document detail (including extracted financial values) for the
 * review sheet -- fetched only while `documentId` is non-null (see
 * `enabled` on `useAsyncData`) and `null` while a row's sheet is closed, so
 * opening one document's review doesn't fetch detail for every row on the
 * page.
 */
export function useDocumentDetail(documentId: number | null, options?: UseAsyncDataOptions): AsyncDataState<DocumentDetail> {
  return useAsyncData(() => getDocument(documentId as number), {
    ...options,
    deps: [documentId, ...(options?.deps ?? [])],
    enabled: documentId !== null && (options?.enabled ?? true),
  })
}

// No `pollIntervalMs` -- checked on page load and via a manual "Check now"
// button (`refetch`), not a background poller, per product direction.
export function useAvailableExternalFilings(options?: UseAsyncDataOptions): AsyncDataState<ExternalFiling[]> {
  return useAsyncData(getAvailableExternalFilings, options)
}

// Same no-poll reasoning as useAvailableExternalFilings -- the hidden list
// only changes via this session's own hide/unhide actions.
export function useHiddenExternalFilings(options?: UseAsyncDataOptions): AsyncDataState<ExternalFiling[]> {
  return useAsyncData(getHiddenExternalFilings, options)
}
