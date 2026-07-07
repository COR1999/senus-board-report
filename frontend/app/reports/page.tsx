'use client'

import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { ReportsTable } from '@/components/dashboard/reports-table'
import { ErrorBanner } from '@/components/error-banner'
import { useReports } from '@/lib/hooks/use-dashboard-data'

export default function ReportsPage() {
  const { data: reports, loading, error, refetch } = useReports()

  return (
    <DashboardShell title="Reports" description="All generated board reports">
      {error && <ErrorBanner error={error} />}
      {loading ? (
        <div className="animate-pulse h-64 bg-muted rounded" />
      ) : (
        <ReportsTable reports={reports ?? []} onRegenerated={refetch} />
      )}
    </DashboardShell>
  )
}
