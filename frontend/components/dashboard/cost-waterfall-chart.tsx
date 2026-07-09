'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { formatCurrencyShort } from '@/lib/format'
import type { CostWaterfall } from '@/lib/data-service'

type WaterfallStepType = 'total' | 'increase' | 'decrease'

export interface WaterfallRow {
  label: string
  /** Bottom of the drawn bar -- min(start, end), so a negative subtotal
   * (e.g. a loss-making Operating Result) still draws the right span. */
  base: number
  /** Height of the drawn bar -- abs(end - start). */
  display: number
  /** The real cumulative value this step ends on -- shown in the tooltip. */
  end: number
  type: WaterfallStepType
}

const TOTAL_COLOR = '#64748b' // slate-500 -- a subtotal/total anchor, not a cost or an add-back
const INCREASE_COLOR = '#10b981' // emerald-500
const DECREASE_COLOR = '#f43f5e' // rose-500

function colorFor(type: WaterfallStepType): string {
  if (type === 'total') return TOTAL_COLOR
  return type === 'increase' ? INCREASE_COLOR : DECREASE_COLOR
}

/**
 * Pure data-shaping step behind the waterfall -- same reasoning as
 * revenue-chart.tsx's buildChartRows (ResponsiveContainer never renders its
 * children under jsdom, so this is the actual logic worth unit-testing
 * directly). Each row is a (start, end) span, not a signed delta, so a
 * genuinely negative subtotal draws correctly below the axis instead of
 * assuming every figure in a real filing is positive.
 *
 * "Operating Costs" (Gross Profit -> Operating Result) is deliberately NOT
 * split into administrative expenses vs. anything else -- no R&D or other
 * cost-category line exists in the source filings, and inventing one would
 * fabricate a breakdown the underlying document never disclosed (see
 * docs/dashboard-review.md's "Fixing the charts" section).
 */
export function buildWaterfallRows(data: CostWaterfall): WaterfallRow[] {
  if (
    !data.available ||
    data.revenue == null ||
    data.gross_profit == null ||
    data.operating_result == null ||
    data.ebitda == null
  ) {
    return []
  }

  const steps: { label: string; start: number; end: number; type: WaterfallStepType }[] = [
    { label: 'Revenue', start: 0, end: data.revenue, type: 'total' },
    { label: 'Cost of Sales', start: data.revenue, end: data.gross_profit, type: 'decrease' },
    { label: 'Gross Profit', start: 0, end: data.gross_profit, type: 'total' },
    { label: 'Operating Costs', start: data.gross_profit, end: data.operating_result, type: 'decrease' },
    { label: 'Operating Result', start: 0, end: data.operating_result, type: 'total' },
    { label: 'D&A', start: data.operating_result, end: data.ebitda, type: 'increase' },
    { label: 'EBITDA', start: 0, end: data.ebitda, type: 'total' },
  ]

  return steps.map(({ label, start, end, type }) => ({
    label,
    base: Math.min(start, end),
    display: Math.abs(end - start),
    end,
    type,
  }))
}

function WaterfallTooltip({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload || payload.length === 0) return null
  const row = payload[0]?.payload as WaterfallRow | undefined
  if (!row) return null
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <div className="mb-1 text-xs font-medium text-muted-foreground">{row.label}</div>
      <div className="text-sm font-semibold text-foreground">{formatCurrencyShort(row.end)}</div>
    </div>
  )
}

interface CostWaterfallChartProps {
  data: CostWaterfall
  periodLabel?: string | null
}

/**
 * Revenue -> Cost of Sales -> Gross Profit -> Operating Costs -> Operating
 * Result -> D&A -> EBITDA, per docs/dashboard-review.md's chart-selection
 * guidance. Renders nothing at all when the selected period's filing
 * doesn't disclose a full cost breakdown (e.g. the FY2025 Information
 * Document, a summary-table-only prospectus) -- same adaptive discipline
 * as every other widget on this dashboard, never a waterfall with a
 * fabricated or silently-zeroed gap.
 */
export function CostWaterfallChart({ data, periodLabel }: CostWaterfallChartProps) {
  const rows = buildWaterfallRows(data)
  if (rows.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost Waterfall</CardTitle>
        {periodLabel && <CardDescription>{periodLabel}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={rows} accessibilityLayer={false} margin={{ left: 4, right: 12, top: 8, bottom: 8 }}>
            <CartesianGrid vertical={false} stroke="currentColor" className="text-foreground/10" />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tickMargin={10}
              interval={0}
              // Angled, not horizontal -- seven category labels (some as
              // long as "Operating Result"/"Administrative Expenses") never
              // fit un-rotated on a narrow chart without overlapping into
              // an unreadable smear (confirmed on a real 375px-wide phone).
              angle={-40}
              textAnchor="end"
              height={54}
              tick={{ fill: 'currentColor', fontSize: 10 }}
              className="text-muted-foreground"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tickMargin={8}
              tick={{ fill: 'currentColor', fontSize: 12 }}
              className="text-muted-foreground"
              tickFormatter={formatCurrencyShort}
              width={68}
            />
            {/* `cursor={false}` -- Recharts' default Bar tooltip cursor
                draws a full-height, unstyled gray/white rectangle behind
                the hovered/tapped column, which read as a stray white box
                over this card's dark theme (confirmed on a real phone).
                WaterfallTooltip's own content already identifies the
                hovered bar, so the extra highlight rectangle was pure
                chart junk, not information. */}
            <Tooltip cursor={false} content={(props) => <WaterfallTooltip {...props} />} />
            {/* Invisible spacer bar (the "floating" part of the waterfall
                effect) stacked under the real, colored delta/subtotal bar. */}
            <Bar dataKey="base" stackId="waterfall" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="display" stackId="waterfall" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {rows.map((row) => (
                <Cell key={row.label} fill={colorFor(row.type)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: TOTAL_COLOR }} />
            Subtotal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: DECREASE_COLOR }} />
            Cost
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: INCREASE_COLOR }} />
            Add-back
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
