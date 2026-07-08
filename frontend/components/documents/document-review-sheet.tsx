'use client'

import { useState } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ClipboardCheck, Eye, CheckCircle2 } from 'lucide-react'
import { type DocumentItem, type DocumentFinancialMetrics } from '@/lib/data-service'
import { formatCurrencyShort } from '@/lib/format'
import { useDocumentDetail } from '@/lib/hooks/use-dashboard-data'
import { useApproveDocument } from '@/lib/hooks/use-mutations'
import { ErrorBanner } from '@/components/error-banner'

interface DocumentReviewSheetProps {
  document: DocumentItem
  /** Called after a successful approve -- the caller refetches its own
   * document list (same "refetch on mutation success" pattern as every
   * other mutation hook on this page, see useDeleteDocument/useHideExternalFiling).
   * Never invoked for a `rejected` document -- there's no approve action
   * to trigger it (see the view-only rendering below). */
  onApproved: () => void
}

/** One extracted-value row, e.g. "Revenue" / "€355K". `null` renders as
 * "Not reported" rather than "€0" or a blank -- a missing figure and a
 * genuine zero are different facts (see Metrics' own `history` field docs
 * in data-service.ts for the same convention elsewhere in this app). */
function MetricRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-center justify-between border-b border-border/40 py-2.5 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium tabular-nums">{value ?? 'Not reported'}</span>
    </div>
  )
}

function formatMetricValue(metrics: DocumentFinancialMetrics, key: keyof DocumentFinancialMetrics): string | null {
  const value = metrics[key]
  if (value === null) return null
  if (key === 'customers') return `${value}`
  if (key === 'gross_margin' || key === 'operating_margin') return `${value}%`
  return formatCurrencyShort(value as number)
}

/**
 * Side panel for reviewing a `needs_review` or `rejected` document's
 * actual extracted values and the confidence gate's own reasons. A
 * `needs_review` document can be approved onto the dashboard from here
 * (POST /api/documents/{id}/approve, see FinancialMetrics.human_approved_at);
 * a `rejected` one is strictly view-only -- it scored too low to ever be
 * trustworthy enough for the dashboard, and there's no approve path for it
 * (see the backend's `approve_document`, which 400s on anything but
 * `needs_review`). Only ever rendered for one of those two tiers -- see
 * the trigger buttons in documents/page.tsx.
 */
export function DocumentReviewSheet({ document, onApproved }: DocumentReviewSheetProps) {
  const [open, setOpen] = useState(false)
  const { data: detail, loading, error: loadError } = useDocumentDetail(open ? document.id : null)
  const { approve, approvingId, error: approveError } = useApproveDocument(() => {
    setOpen(false)
    onApproved()
  })

  const isRejected = document.extraction_confidence_tier === 'rejected'
  const error = loadError || approveError
  const metrics = detail?.financial_metrics ?? null
  const isApproving = approvingId === document.id

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 w-8 p-0 text-muted-foreground"
        onClick={() => setOpen(true)}
        title={isRejected ? 'View why this document was rejected' : 'Review extracted figures before approving for the dashboard'}
      >
        {isRejected ? <Eye className="h-5 w-5" /> : <ClipboardCheck className="h-5 w-5" />}
        <span className="sr-only">Review {document.filename}</span>
      </Button>
      <SheetContent>
        <SheetHeader>
          <SheetTitle className="truncate">{document.filename}</SheetTitle>
          <SheetDescription>
            {isRejected
              ? "This document's extraction scored too low to be trusted -- it's kept here for reference, but can never drive the dashboard. Check the reasons and any values found below against the source PDF."
              : "This document's extraction scored below the auto-accept threshold. Check the figures below against the source PDF, then approve it to unlock the dashboard's headline KPIs."}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4">
          {error && <ErrorBanner error={error} />}
          {loading && <div className="animate-pulse h-40 bg-muted rounded" />}
          {!loading && metrics && (
            <>
              <div className="flex items-center gap-2">
                <Badge
                  variant={isRejected ? 'destructive' : 'outline'}
                  className={isRejected ? undefined : 'border-border/60 bg-muted text-muted-foreground'}
                >
                  {metrics.extraction_confidence != null ? `${metrics.extraction_confidence}% confidence` : 'Not yet scored'}
                </Badge>
              </div>
              <div>
                <MetricRow label="Revenue" value={formatMetricValue(metrics, 'revenue')} />
                <MetricRow label="Customers" value={formatMetricValue(metrics, 'customers')} />
                <MetricRow label="Cash" value={formatMetricValue(metrics, 'cash')} />
                <MetricRow label="EBITDA" value={formatMetricValue(metrics, 'ebitda')} />
                <MetricRow label="Gross margin" value={formatMetricValue(metrics, 'gross_margin')} />
                <MetricRow label="Operating margin" value={formatMetricValue(metrics, 'operating_margin')} />
              </div>
              {metrics.extraction_confidence_reasons && metrics.extraction_confidence_reasons.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-sm font-medium text-foreground">Why this score</span>
                  <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                    {metrics.extraction_confidence_reasons.map((reason, i) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          {!loading && !metrics && !error && (
            <p className="text-sm text-muted-foreground">No extracted figures found for this document.</p>
          )}
        </div>
        {!isRejected && (
          <SheetFooter>
            <Button onClick={() => approve(document.id)} disabled={isApproving || loading || !metrics}>
              <CheckCircle2 className="h-4 w-4" />
              {isApproving ? 'Approving...' : 'Approve for dashboard'}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  )
}
