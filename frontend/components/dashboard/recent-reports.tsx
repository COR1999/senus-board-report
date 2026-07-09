'use client'

import Link from 'next/link'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { capitalize } from '@/lib/utils'
import { REPORT_STATUS_STYLES, reportDisplayName } from '@/lib/report-display'
import type { Report } from '@/lib/data-service'

interface RecentReportsProps {
  reports: Report[]
  /** How many rows to show -- an at-a-glance pointer to what's recent, not
   * the full table. @default 3 */
  limit?: number
}

/**
 * A short "what's recent" pointer for the executive dashboard's closing
 * section -- the full searchable/filterable/exportable ReportsTable (with
 * a status filter, period filter, CSV export, and a per-row regenerate
 * action) belongs on the dedicated /reports page, one click away via the
 * sidebar. Repeating that full table's chrome at the bottom of an
 * at-a-glance executive page was clutter earned by component reuse, not by
 * what a board reader actually needs there -- see
 * docs/dashboard-review.md's "Proposed page structure" section.
 */
export function RecentReports({ reports, limit = 3 }: RecentReportsProps) {
  const recent = [...reports]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, limit)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Reports</CardTitle>
        <CardDescription>Latest financial and board reports</CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/reports">View all</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {recent.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No reports available</p>
        ) : (
          <div className="divide-y divide-border/40">
            {recent.map((report) => (
              <div key={report.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{reportDisplayName(report)}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(report.created_at).toLocaleDateString('en-US', {
                      year: 'numeric', month: 'short', day: 'numeric',
                    })}
                  </p>
                </div>
                <Badge className={REPORT_STATUS_STYLES[report.status]}>{capitalize(report.status)}</Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
