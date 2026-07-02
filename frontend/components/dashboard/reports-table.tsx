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
import { Download } from 'lucide-react'

const reports = [
  {
    id: 1,
    name: 'Q4 2025 Financial Report',
    date: '2025-12-31',
    status: 'completed',
  },
  {
    id: 2,
    name: 'Q3 2025 Board Report',
    date: '2025-09-30',
    status: 'completed',
  },
  {
    id: 3,
    name: 'H1 2025 Investor Update',
    date: '2025-06-30',
    status: 'completed',
  },
  {
    id: 4,
    name: 'Q1 2025 Performance Review',
    date: '2025-03-31',
    status: 'completed',
  },
]

export function ReportsTable() {
  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Recent Reports</CardTitle>
        <CardDescription>Latest financial and board reports</CardDescription>
      </CardHeader>
      <CardContent>
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
            {reports.map((report) => (
              <TableRow key={report.id} className="border-border/40">
                <TableCell className="font-medium">{report.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {new Date(report.date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </TableCell>
                <TableCell>
                  <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                    {report.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 hover:bg-muted/50"
                  >
                    <Download className="h-4 w-4" />
                    <span className="sr-only">Download report</span>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}