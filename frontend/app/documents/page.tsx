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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Trash2, Upload, Download, DownloadCloud, RefreshCw, EyeOff, RotateCcw } from 'lucide-react'
import { type DocumentItem, getDocumentFileUrl } from '@/lib/data-service'
import { DocumentReviewSheet } from '@/components/documents/document-review-sheet'
import { formatFileSize } from '@/lib/format'
import { capitalize } from '@/lib/utils'
import { useDocuments, useAvailableExternalFilings, useHiddenExternalFilings } from '@/lib/hooks/use-dashboard-data'
import {
  useUploadDocument,
  useDeleteDocument,
  useImportExternalFiling,
  useHideExternalFiling,
  useUnhideExternalFiling,
} from '@/lib/hooks/use-mutations'
import { ErrorBanner } from '@/components/error-banner'
import { buildPeriodOptions, matchesPeriod } from '@/lib/period-filter'
import { MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_LABEL } from '@/lib/upload-constraints'

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
  const {
    data: availableFilings,
    loading: loadingAvailableFilings,
    error: availableFilingsError,
    refetch: refetchAvailableFilings,
  } = useAvailableExternalFilings()
  const { importFiling, importingId, error: importError } = useImportExternalFiling(() => {
    refetch()
    refetchAvailableFilings()
  })
  const {
    data: hiddenFilings,
    loading: loadingHiddenFilings,
    refetch: refetchHiddenFilings,
  } = useHiddenExternalFilings()
  const { hideFiling, hidingId, error: hideError } = useHideExternalFiling(() => {
    refetchAvailableFilings()
    refetchHiddenFilings()
  })
  const { unhideFiling, unhidingId, error: unhideError } = useUnhideExternalFiling(() => {
    refetchAvailableFilings()
    refetchHiddenFilings()
  })
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [search, setSearch] = useState('')
  const [periodFilter, setPeriodFilter] = useState('all')
  const [sizeError, setSizeError] = useState<string | null>(null)

  const error = loadError || uploadError || deleteError || sizeError || importError || hideError || unhideError

  // Only created_at (upload date) exists on a document -- there's no
  // reporting-period concept at this level (that only exists on the
  // generated Report, a separate entity), so this is an upload-date filter.
  const periodOptions = useMemo(() => buildPeriodOptions((documents ?? []).map((d) => d.created_at)), [documents])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (documents ?? []).filter((doc) => {
      if (periodFilter !== 'all' && !matchesPeriod(doc.created_at, periodFilter)) return false
      if (!query) return true
      return doc.filename.toLowerCase().includes(query)
    })
  }, [documents, search, periodFilter])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      setSizeError(`"${file.name}" is ${formatFileSize(file.size)}, which is over the ${MAX_UPLOAD_SIZE_LABEL} upload limit.`)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    setSizeError(null)

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
      {!loadingAvailableFilings && (availableFilings ?? []).length > 0 && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base">
                  {/* A single template-literal expression, not interleaved JSX
                      text/expressions -- splitting this across source lines
                      previously trimmed the space right after the
                      pluralization expression, rendering "filingsavailable". */}
                  {`${availableFilings!.length} new filing${availableFilings!.length === 1 ? '' : 's'} available from Senus's investor relations page`}
                </CardTitle>
                <CardDescription>Found via Senus&apos;s investor relations API -- import to add it to this dashboard.</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={refetchAvailableFilings}>
                <RefreshCw className="h-4 w-4" />
                Check now
              </Button>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {availableFilings!.map((filing) => (
              <div
                key={filing.attachment_id}
                className="flex items-center justify-between gap-3 rounded-md border border-border/40 bg-background px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{filing.file_name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(filing.file_size)}
                    {filing.published_date &&
                      ` · Published ${new Date(filing.published_date).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })}`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => importFiling(filing.attachment_id)}
                    // Disabled whenever *any* import is in flight, not just
                    // this row's own -- `useImportExternalFiling` tracks a
                    // single `importingId`, so triggering a second import
                    // before the first resolves would let one request's
                    // result silently overwrite the other's error/success
                    // state. One import at a time avoids the race entirely.
                    disabled={importingId !== null}
                  >
                    <DownloadCloud className="h-4 w-4" />
                    {importingId === filing.attachment_id ? 'Importing...' : 'Import'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 w-9 p-0 text-muted-foreground"
                    onClick={() => hideFiling(filing.attachment_id)}
                    disabled={hidingId !== null}
                    title="Mark as out of scope -- no financial data in this filing"
                  >
                    <EyeOff className="h-4 w-4" />
                    <span className="sr-only">Mark {filing.file_name} as out of scope</span>
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {!loadingAvailableFilings && (availableFilings ?? []).length === 0 && (
        <div className="flex items-center justify-between gap-3 px-1 text-sm text-muted-foreground">
          <span>No new filings from Senus&apos;s investor relations page.</span>
          <Button variant="ghost" size="sm" onClick={refetchAvailableFilings}>
            <RefreshCw className="h-4 w-4" />
            Check now
          </Button>
        </div>
      )}
      {!loadingHiddenFilings && (hiddenFilings ?? []).length > 0 && (
        <Card className="border-border/40">
          <CardHeader>
            <CardTitle className="text-base">Out of scope ({hiddenFilings!.length})</CardTitle>
            <CardDescription>
              Filings marked as not applicable (no extractable financial data) -- restore one if you
              change your mind.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {hiddenFilings!.map((filing) => (
              <div
                key={filing.attachment_id}
                className="flex items-center justify-between gap-3 rounded-md border border-border/40 bg-background px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-muted-foreground">{filing.file_name}</p>
                  <p className="text-sm text-muted-foreground">{formatFileSize(filing.file_size)}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => unhideFiling(filing.attachment_id)}
                  disabled={unhidingId !== null}
                >
                  <RotateCcw className="h-4 w-4" />
                  {unhidingId === filing.attachment_id ? 'Restoring...' : 'Restore'}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
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
                <Select value={periodFilter} onValueChange={setPeriodFilter}>
                  <SelectTrigger aria-label="Filter by period" className="whitespace-nowrap">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All periods</SelectItem>
                    {periodOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge className={STATUS_STYLES[doc.status] ?? 'bg-muted text-foreground'}>
                              {capitalize(doc.status)}
                            </Badge>
                            {doc.extraction_confidence_tier === 'needs_review' && (
                              <>
                                <Badge
                                  variant="outline"
                                  className="border-border/60 bg-muted text-muted-foreground"
                                  title="This document's extracted figures scored below the auto-accept confidence threshold -- they're saved, but excluded from the dashboard's headline KPIs until reviewed."
                                >
                                  Pending Review
                                </Badge>
                                <DocumentReviewSheet document={doc} onApproved={refetch} />
                              </>
                            )}
                          </div>
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
