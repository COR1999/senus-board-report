'use client'

import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { ReportsTable } from '@/components/dashboard/reports-table'
import { useReports } from '@/lib/hooks/use-dashboard-data'

export default function ReportsPage() {
  const { data: reports, loading, error, refetch } = useReports()

  return (
    <DashboardShell title="Reports" description="All generated board reports">
      {error && (
        <div className="mb-4 text-red-600 bg-red-50 dark:bg-red-950 p-4 rounded-lg">
          Error: {error}
        </div>
      )}
      {loading ? (
        <div className="animate-pulse h-64 bg-muted rounded" />
      ) : (
        <ReportsTable reports={reports ?? []} onRegenerated={refetch} />
      )}
    </DashboardShell>
  )
}
