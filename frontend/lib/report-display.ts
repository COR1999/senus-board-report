// lib/report-display.ts
//
// Shared between reports-table.tsx (the full /reports page) and
// recent-reports.tsx (the dashboard's short pointer list) -- both render
// the same Report rows, just with different amounts of surrounding chrome,
// so the status-color mapping and display-name fallback shouldn't drift
// into two copies.
import type { Report } from '@/lib/data-service'

export const REPORT_STATUS_STYLES: Record<Report['status'], string> = {
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  generating: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400',
}

/** Falls back to a document-number label when no company name was extracted
 * (e.g. the report is still generating, or extraction found nothing usable). */
export function reportDisplayName(report: Report): string {
  const name = report.summary?.company_name
  return name && name.trim().length > 0 ? name : `Document #${report.document_id}`
}
