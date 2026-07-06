import type { Report } from '@/lib/data-service'

/** Wraps a field in quotes and escapes embedded quotes if it needs CSV escaping. */
function csvField(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

/** Builds CSV text (not written to disk) -- split out from exportReportsToCsv so it's unit-testable without touching the DOM. */
export function reportsToCsv(reports: Report[]): string {
  const header = ['Report Name', 'Reporting Period', 'Status', 'Created At']
  const rows = reports.map((report) => [
    report.summary?.company_name ?? `Document #${report.document_id}`,
    report.summary?.reporting_period ?? '',
    report.status,
    report.created_at,
  ])

  return [header, ...rows].map((row) => row.map(csvField).join(',')).join('\n')
}

/** Triggers a browser download of `reports` as a CSV file. No-op if there's nothing to export. */
export function exportReportsToCsv(reports: Report[], filename = 'reports.csv'): void {
  if (reports.length === 0) return

  const csv = reportsToCsv(reports)
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()

  URL.revokeObjectURL(url)
}
