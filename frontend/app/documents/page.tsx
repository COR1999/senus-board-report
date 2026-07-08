'use client'

import { useMemo, useRef, useState } from 'react'
import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Trash2, Upload, CalendarRange, Download } from 'lucide-react'
import { type DocumentItem, getDocumentFileUrl } from '@/lib/data-service'
import { formatFileSize } from '@/lib/format'
import { capitalize } from '@/lib/utils'
import { useDocuments } from '@/lib/hooks/use-dashboard-data'
import { useUploadDocument, useDeleteDocument } from '@/lib/hooks/use-mutations'
import { ErrorBanner } from '@/components/error-banner'

// Same status-color convention as reports-table.tsx's STATUS_STYLES.
// DocumentItem.status is a plain string (not a fixed union like Report's),
// so unrecognized values fall back to a neutral badge rather than crashing.
const STATUS_STYLES: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400',
}

export default function DocumentsPage() {
  const { data: documents, loading, error: loadError, refetch } = useDocuments()
  const { upload, uploading, error: uploadError } = useUploadDocument(refetch)
  const { remove, deletingId, error: deleteError } = useDeleteDocument(refetch)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [search, setSearch] = useState('')

  const error = loadError || uploadError || deleteError

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return documents ?? []
    return (documents ?? []).filter((doc) => doc.filename.toLowerCase().includes(query))
  }, [documents, search])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    await upload(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDelete = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${doc.filename}"? This also removes its extracted metrics and report.`)) {
      return
    }

    await remove(doc.id)
  }

  return (
    <DashboardShell title="Documents" description="Uploaded financial reports and filings">
      {error && <ErrorBanner error={error} />}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Uploaded Documents</CardTitle>
              <CardDescription>PDF financial reports processed by Senus</CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <Upload className="h-4 w-4" />
              {uploading ? 'Uploading...' : 'Upload PDF'}
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="animate-pulse h-32 bg-muted rounded" />
          ) : (
            <>
              <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Input
                  placeholder="Search documents..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Search documents"
                  className="sm:max-w-sm"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled
                  title="Filter by year/month coming soon"
                >
                  <CalendarRange className="h-4 w-4" />
                  <span className="sr-only">Filter by year/month (coming soon)</span>
                  Filter by period
                </Button>
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="border-border/40 hover:bg-transparent">
                    <TableHead>Filename</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Uploaded</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.length > 0 ? (
                    filtered.map((doc) => (
                      <TableRow key={doc.id} className="border-border/40">
                        <TableCell className="font-medium">{doc.filename}</TableCell>
                        <TableCell>
                          <Badge className={STATUS_STYLES[doc.status] ?? 'bg-muted text-foreground'}>
                            {capitalize(doc.status)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{formatFileSize(doc.file_size)}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(doc.created_at).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end">
                            {/* Plain download link, not a fetch/blob helper --
                                the browser handles the download itself once the
                                backend sets Content-Disposition, and a direct
                                navigation isn't subject to CORS the way a
                                cross-origin `fetch` would be. May 404 with a
                                specific message if the file wasn't retained
                                across a backend redeploy (see getDocumentFileUrl). */}
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" asChild>
                              <a href={getDocumentFileUrl(doc.id)} download={doc.filename}>
                                <Download className="h-5 w-5" />
                                <span className="sr-only">Download {doc.filename}</span>
                              </a>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                              onClick={() => handleDelete(doc)}
                              disabled={deletingId === doc.id}
                            >
                              <Trash2 className="h-4 w-4" />
                              <span className="sr-only">Delete {doc.filename}</span>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        {(documents ?? []).length === 0 ? 'No documents uploaded yet' : 'No documents match your search'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>
    </DashboardShell>
  )
}
