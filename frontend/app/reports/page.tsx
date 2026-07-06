'use client'

import { useEffect, useState } from 'react'
import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { ReportsTable } from '@/components/dashboard/reports-table'
import { getReports, type Report } from '@/lib/data-service'

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getReports().then((data) => {
      setReports(data)
      setLoading(false)
    })
  }, [])

  return (
    <DashboardShell title="Reports" description="All generated board reports">
      {loading ? (
        <div className="animate-pulse h-64 bg-muted rounded" />
      ) : (
        <ReportsTable reports={reports} />
      )}
    </DashboardShell>
  )
}
