'use client'

import { useRef } from 'react'
import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Trash2, Upload } from 'lucide-react'
import { type DocumentItem } from '@/lib/data-service'
import { useDocuments } from '@/lib/hooks/use-dashboard-data'
import { useUploadDocument, useDeleteDocument } from '@/lib/hooks/use-mutations'

export default function DocumentsPage() {
  const { data: documents, loading, error: loadError, refetch } = useDocuments()
  const { upload, uploading, error: uploadError } = useUploadDocument(refetch)
  const { remove, deletingId, error: deleteError } = useDeleteDocument(refetch)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const error = loadError || uploadError || deleteError

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
      {error && (
        <div className="mb-4 text-red-600 bg-red-50 dark:bg-red-950 p-4 rounded-lg">
          Error: {error}
        </div>
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
            <Table>
              <TableHeader>
                <TableRow className="border-border/40 hover:bg-transparent">
                  <TableHead>Filename</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(documents ?? []).length > 0 ? (
                  (documents ?? []).map((doc) => (
                    <TableRow key={doc.id} className="border-border/40">
                      <TableCell className="font-medium">{doc.filename}</TableCell>
                      <TableCell>
                        <Badge className="bg-muted text-foreground">{doc.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(doc.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </TableCell>
                      <TableCell className="text-right">
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
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                      No documents uploaded yet
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </DashboardShell>
  )
}
