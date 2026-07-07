'use client'

import { useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Download, RefreshCw, CalendarRange } from 'lucide-react'
import { type Report } from '@/lib/data-service'
import { exportReportsToCsv } from '@/lib/export-csv'
import { capitalize } from '@/lib/utils'
import { useRegenerateReport } from '@/lib/hooks/use-mutations'

interface ReportsTableProps {
  reports?: Report[]
  /** Called after a report finishes regenerating, so the parent can re-fetch the list. */
  onRegenerated?: () => void
}

const STATUS_STYLES: Record<Report['status'], string> = {
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  generating: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400',
}

const STATUS_OPTIONS: Array<Report['status'] | 'all'> = ['all', 'completed', 'generating', 'pending', 'failed']

function reportDisplayName(report: Report): string {
  const name = report.summary?.company_name
  return name && name.trim().length > 0 ? name : `Document #${report.document_id}`
}

export function ReportsTable({ reports = [], onRegenerated }: ReportsTableProps) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<Report['status'] | 'all'>('all')
  const { regenerate, regeneratingId, error } = useRegenerateReport(onRegenerated)

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return reports.filter((report) => {
      if (statusFilter !== 'all' && report.status !== statusFilter) return false
      if (!query) return true
      const haystack = `${reportDisplayName(report)} ${report.summary?.reporting_period ?? ''}`.toLowerCase()
      return haystack.includes(query)
    })
  }, [reports, search, statusFilter])

  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Recent Reports</CardTitle>
        <CardDescription>Latest financial and board reports</CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 text-sm text-rose-600 dark:text-rose-400" role="alert">
            {error}
          </div>
        )}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-1 flex-col gap-2 sm:max-w-sm sm:flex-row">
            <Input
              placeholder="Search reports..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search reports"
            />
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as Report['status'] | 'all')}>
              <SelectTrigger aria-label="Filter by status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option === 'all' ? 'All statuses' : capitalize(option)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled
              title="Filter by year/month coming soon"
            >
              <CalendarRange className="h-5 w-5" />
              <span className="sr-only">Filter by year/month (coming soon)</span>
              Filter by period
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportReportsToCsv(filtered)}
              disabled={filtered.length === 0}
            >
              <Download className="h-5 w-5" />
              Export CSV
            </Button>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow className="border-border/40 hover:bg-transparent">
              <TableHead>Report Name</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length > 0 ? (
              filtered.map((report) => (
                <TableRow key={report.id} className="border-border/40">
                  <TableCell className="font-medium">{reportDisplayName(report)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(report.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </TableCell>
                  <TableCell>
                    <Badge className={STATUS_STYLES[report.status]}>{capitalize(report.status)}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 hover:bg-muted/50"
                        onClick={() => regenerate(report.id)}
                        disabled={regeneratingId === report.id}
                        title="Regenerate report"
                      >
                        <RefreshCw className={`h-5 w-5 ${regeneratingId === report.id ? 'animate-spin' : ''}`} />
                        <span className="sr-only">Regenerate report for {reportDisplayName(report)}</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        disabled
                        title="PDF export coming later"
                      >
                        <Download className="h-5 w-5" />
                        <span className="sr-only">Download report (PDF export coming later)</span>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                  {reports.length === 0 ? 'No reports available' : 'No reports match your filters'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
