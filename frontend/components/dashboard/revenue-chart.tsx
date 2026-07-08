// components/dashboard/revenue-chart.tsx
'use client'

import { useMemo, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { type ChartDataPoint } from '@/lib/data-service'
import { projectSeries } from '@/lib/forecast'
import { formatCurrencyShort } from '@/lib/format'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface RevenueChartProps {
  data: ChartDataPoint[]
  /** Real reporting period for context under the title, e.g. "Jul 2025 - Dec 2025". */
  periodLabel?: string | null
  /** The currently-selected report's document_id (see the dashboard's period
   * selector) -- highlights that one point on the chart, without filtering
   * the rest of the history out. `null` (the true-latest default) means no
   * point is specially highlighted. */
  selectedDocumentId?: number | null
}

export type MetricKey = 'revenue' | 'ebitda' | 'cash'

// Series-swap toggle, not a dual-axis overlay: Revenue/EBITDA/Cash are on
// very different scales and can have different signs (EBITDA is currently
// negative), so only one is ever plotted at a time on a single y-axis.
// Forecasting (a simple linear trendline, see lib/forecast.ts) is available
// for all three -- with only a handful of real data points today the
// projection is a rough visual trend, not a real financial model, same
// caveat for every metric.
//
// Each metric has two colors, not one: `color` for the Full-Year line,
// `hyColor` a lighter tint of the same hue for the Half-Year line -- related
// but clearly distinguishable, and deliberately NOT the forecast overlay's
// dashed/indigo treatment (which must stay uniquely "this is projected, not
// real" -- see FORECAST_COLOR below).
const METRICS: Record<MetricKey, { label: string; color: string; hyColor: string }> = {
  revenue: { label: 'Revenue', color: '#10b981', hyColor: '#6ee7b7' }, // emerald-500 / emerald-300
  ebitda: { label: 'EBITDA', color: '#f59e0b', hyColor: '#fcd34d' }, // amber-500 / amber-300
  cash: { label: 'Cash', color: '#2a78d6', hyColor: '#93c5fd' }, // blue-ish / blue-300
}

// A point whose cadence couldn't be split into either line -- rendered as an
// isolated marker (no connecting line, see the `other` series below) rather
// than guessed into Full Year or Half Year. In practice this almost never
// fires for real data (every real filing's cadence is deterministically
// detected -- see backend's _cadence_months), but a point genuinely missing
// both reporting_period_start/_end must not be silently misplaced.
const OTHER_COLOR = '#94a3b8' // slate-400

const FORECAST_PERIODS = 3
const FORECAST_COLOR = '#6366f1'

export type CadenceBucket = 'fy' | 'hy' | 'other'

// Full-year (>=9mo) vs. half-year (<=6mo) vs. undeterminable -- the real
// extractor only ever produces 6 or 12 in practice (see
// FinancialMetricsExtractor's cadence-cue detection), so the 7/8mo gap is a
// defensive catch-all, not a case expected to fire on real data.
export function cadenceBucket(cadenceMonths: number | null): CadenceBucket {
  if (cadenceMonths == null) return 'other'
  if (cadenceMonths <= 6) return 'hy'
  if (cadenceMonths >= 9) return 'fy'
  return 'other'
}

function lastIndexWhere<T>(items: T[], predicate: (item: T) => boolean): number {
  for (let i = items.length - 1; i >= 0; i--) {
    if (predicate(items[i])) return i
  }
  return -1
}

/** One row of the combined chart dataset -- every real `ChartDataPoint`
 * field, plus the per-bucket series values Recharts actually plots. Only
 * one of `fy`/`hy`/`other` is ever non-null for a given row (a point
 * belongs to exactly one bucket); `connectNulls={false}` on each `<Area>`
 * means the other two series simply skip drawing at this x-position. */
export interface ChartRow extends Partial<ChartDataPoint> {
  period: string
  fy: number | null
  hy: number | null
  other: number | null
  fy_forecast: number | null
  hy_forecast: number | null
}

/**
 * Pure data-shaping step behind the chart -- extracted out of the `useMemo`
 * below so it's unit-testable without Recharts/jsdom (`ResponsiveContainer`
 * measures 0 width in jsdom and never renders its children, so chart
 * internals like the legend or per-point dots aren't observable from a
 * component test; this function is the actual logic worth covering
 * directly). See the `useMemo` call site for the full design rationale
 * (per-cadence independent forecasts merged by index).
 */
export function buildChartRows(data: ChartDataPoint[], metric: MetricKey, showForecast: boolean): ChartRow[] {
  const rows: ChartRow[] = data.map((point) => {
    const bucket = cadenceBucket(point.cadence_months)
    return {
      ...point,
      fy: bucket === 'fy' ? point[metric] : null,
      hy: bucket === 'hy' ? point[metric] : null,
      other: bucket === 'other' ? point[metric] : null,
      fy_forecast: null,
      hy_forecast: null,
    }
  })

  if (!showForecast) return rows

  // Handoff: the LAST real point of each cadence also carries its own
  // value under that cadence's `_forecast` key, so the solid and dashed
  // segments visually join at one shared point instead of leaving a gap.
  const lastFyIndex = lastIndexWhere(rows, (r) => r.fy !== null)
  const lastHyIndex = lastIndexWhere(rows, (r) => r.hy !== null)
  if (lastFyIndex !== -1) rows[lastFyIndex] = { ...rows[lastFyIndex], fy_forecast: rows[lastFyIndex].fy }
  if (lastHyIndex !== -1) rows[lastHyIndex] = { ...rows[lastHyIndex], hy_forecast: rows[lastHyIndex].hy }

  const fyHistory = data.filter((p) => cadenceBucket(p.cadence_months) === 'fy')
  const hyHistory = data.filter((p) => cadenceBucket(p.cadence_months) === 'hy')
  const fyForecast = fyHistory.length > 0 ? projectSeries(fyHistory, metric, FORECAST_PERIODS) : []
  const hyForecast = hyHistory.length > 0 ? projectSeries(hyHistory, metric, FORECAST_PERIODS) : []

  if (fyForecast.length === 0 && hyForecast.length === 0) return rows

  const forecastRows: ChartRow[] = Array.from({ length: FORECAST_PERIODS }, (_, i) => ({
    period: fyForecast[i]?.period ?? hyForecast[i]?.period ?? `Next Report ${i + 1}`,
    fy: null,
    hy: null,
    other: null,
    fy_forecast: fyForecast[i]?.[metric] ?? null,
    hy_forecast: hyForecast[i]?.[metric] ?? null,
  }))

  return [...rows, ...forecastRows]
}

// "Next Report N" x-axis ticks (see lib/forecast.ts) get the same indigo
// used for the dashed forecast line/legend, in italics, so a projected
// period visually reads as distinct from a real historical one instead of
// looking like plain axis text.
interface ForecastAwareTickProps {
  x?: number
  y?: number
  payload?: { value?: string }
}

function ForecastAwareTick({ x = 0, y = 0, payload }: ForecastAwareTickProps) {
  const value = payload?.value ?? ''
  const isForecast = value.startsWith('Next Report ')
  return (
    <text
      x={x}
      y={y + 10}
      textAnchor="middle"
      fontSize={12}
      fontStyle={isForecast ? 'italic' : 'normal'}
      fill={isForecast ? FORECAST_COLOR : 'currentColor'}
      className={isForecast ? undefined : 'text-muted-foreground'}
    >
      {value}
    </text>
  )
}

/**
 * Dot renderer shared by the fy/hy/other series -- a plain colored dot for
 * every real point, except the currently-selected report's own point (see
 * `selectedDocumentId`), which gets a larger dot plus a soft halo so it's
 * unambiguous which period the KPI cards above are describing. Returns
 * nothing for a row where this series has no value (Recharts still calls
 * the dot renderer once per row per series even when `connectNulls={false}`
 * skips the line itself).
 */
function makeSeriesDot(dataKey: 'fy' | 'hy' | 'other', color: string, selectedDocumentId: number | null | undefined) {
  function SeriesDot(props: { cx?: number; cy?: number; payload?: ChartRow }) {
    const { cx, cy, payload } = props
    if (cx == null || cy == null || !payload || payload[dataKey] == null) return null
    const isSelected = selectedDocumentId != null && payload.document_id === selectedDocumentId
    if (isSelected) {
      return (
        <g>
          <circle cx={cx} cy={cy} r={9} fill={color} fillOpacity={0.2} />
          <circle cx={cx} cy={cy} r={5} fill={color} stroke="var(--card)" strokeWidth={2} />
        </g>
      )
    }
    return <circle cx={cx} cy={cy} r={4} fill={color} />
  }
  return SeriesDot
}

/**
 * Custom tooltip, for reasons the default `<Tooltip>` props couldn't fix:
 * (1) Recharts renders one row per *series*, even where that series has no
 * real value at the hovered point -- filtering to entries with a non-null
 * value fixes that. (2) At the point where a real line hands off to its own
 * forecast tail, both series legitimately share the exact same value (see
 * chartData's per-cadence handoff below) -- showing "Full Year: €837K" and
 * "Full Year (projected): €837K" together read as a confusing duplicate, so
 * a forecast entry is dropped whenever it exactly matches a real entry
 * already shown for that same point. (3) The default styling read as too
 * low-contrast; this uses solid opaque colors, a visible border, a real
 * shadow, and bold, larger value text.
 */
function RevenueTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload) return null
  const withValue = payload.filter((entry) => entry.value !== null && entry.value !== undefined)
  const realValues = withValue.filter((entry) => !String(entry.dataKey).endsWith('_forecast')).map((e) => e.value)
  const entries = withValue.filter(
    (entry) => !(String(entry.dataKey).endsWith('_forecast') && realValues.includes(entry.value))
  )
  if (entries.length === 0) return null

  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <div className="mb-1 text-xs font-medium text-muted-foreground">{label}</div>
      {entries.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-sm">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-muted-foreground">{entry.name}:</span>
          <span className="font-semibold text-foreground">
            {typeof entry.value === 'number' ? formatCurrencyShort(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function RevenueChart({ data, periodLabel, selectedDocumentId = null }: RevenueChartProps) {
  const [metric, setMetric] = useState<MetricKey>('revenue')
  const [showForecast, setShowForecast] = useState(false)
  const { label, color, hyColor } = METRICS[metric]

  // Splits `data` into the two real series Recharts actually plots (`fy`/
  // `hy`, plus a rare `other` for an undeterminable cadence), then -- when
  // `showForecast` is on -- projects each cadence's OWN forecast tail
  // independently from that cadence's own historical points (reusing
  // `projectSeries` twice, not inventing a second forecasting algorithm).
  // Both forecast tails are merged into the SAME trailing "Next Report N"
  // rows (matched by index, not appended as separate rows) specifically so
  // a Half-Year projection and a Full-Year projection/actual land at the
  // same x-position -- letting a viewer directly compare "is the full year
  // tracking to what the half-year run-rate implied", the concrete reason
  // this two-line design was chosen over a single blended line.
  const chartData = useMemo<ChartRow[]>(
    () => buildChartRows(data, metric, showForecast),
    [data, showForecast, metric]
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>{label} Trend</CardTitle>
        {periodLabel && (
          <CardDescription className="flex items-center gap-1">
            {periodLabel}
          </CardDescription>
        )}
        <CardAction className="flex items-center gap-4">
          {/* Series-swap toggle: one metric plotted at a time on a single
              y-axis, rather than a dual-axis overlay -- see METRICS above. */}
          <div className="flex items-center gap-1 rounded-lg bg-muted p-0.5">
            {(Object.keys(METRICS) as MetricKey[]).map((key) => (
              <Button
                key={key}
                type="button"
                size="sm"
                variant="ghost"
                // `--secondary` and `--muted` are the exact same color
                // token in this theme, so the old `variant="secondary"`
                // active state was invisible against this row's own
                // `bg-muted` track. An elevated bg-background/shadow pill
                // (the standard segmented-control pattern) uses tokens
                // that are genuinely distinct from `bg-muted` in both
                // light and dark mode.
                className={cn(metric === key && 'bg-background text-foreground shadow-sm')}
                onClick={() => setMetric(key)}
              >
                {METRICS[key].label}
              </Button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Show forecast
            <Switch checked={showForecast} onCheckedChange={setShowForecast} />
          </label>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          {/* accessibilityLayer={false}: Recharts makes the chart surface
              keyboard-focusable by default, which drew an ugly focus-ring
              box on click -- same issue and same fix as KpiSparkline. */}
          <AreaChart data={chartData} accessibilityLayer={false} margin={{ left: 4, right: 12, top: 8 }}>
            <defs>
              <linearGradient id="fyFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="hyFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={hyColor} stopOpacity={0.25} />
                <stop offset="100%" stopColor={hyColor} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={FORECAST_COLOR} stopOpacity={0.15} />
                <stop offset="100%" stopColor={FORECAST_COLOR} stopOpacity={0} />
              </linearGradient>
            </defs>
            {/* Horizontal-only, recessive gridlines -- "minimal gridlines, no
                chart junk" per the boardroom redesign brief. Axis lines/ticks
                dropped in favor of muted labels only. */}
            <CartesianGrid vertical={false} stroke="currentColor" className="text-foreground/10" />
            <XAxis
              dataKey="period"
              axisLine={false}
              tickLine={false}
              tickMargin={10}
              tick={<ForecastAwareTick />}
              padding={{ left: 12, right: 12 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tickMargin={8}
              tick={{ fill: 'currentColor', fontSize: 12 }}
              className="text-muted-foreground"
              tickFormatter={formatCurrencyShort}
              tickCount={5}
              // Wide enough for the longest label this chart ever shows --
              // negative EBITDA (e.g. "-€473.7K") is longer than any
              // Revenue/Cash value, so this must fit that case even when
              // Revenue is the metric currently selected (width doesn't
              // change per-metric, would look like layout jitter on toggle).
              width={68}
            />
            {/* `offset={24}` pushes the box further from the cursor than
                Recharts' 10px default -- at the default offset the box sat
                right on top of the hovered point, hiding the very dot it
                was meant to label. See RevenueTooltip above for why a
                custom content renderer was needed at all. */}
            <Tooltip offset={24} content={(props) => <RevenueTooltip {...props} />} />
            {/* Two real series (Full Year / Half Year) always need a legend
                to tell them apart -- unlike the old single-series chart,
                which only showed one when a forecast overlay was added. */}
            <Legend />
            <Area
              type="monotone"
              dataKey="fy"
              name="Full Year"
              stroke={color}
              strokeWidth={2}
              fill="url(#fyFill)"
              dot={makeSeriesDot('fy', color, selectedDocumentId)}
              activeDot={{ r: 6, strokeWidth: 0, fill: color }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="hy"
              name="Half Year"
              stroke={hyColor}
              strokeWidth={2}
              fill="url(#hyFill)"
              dot={makeSeriesDot('hy', hyColor, selectedDocumentId)}
              activeDot={{ r: 6, strokeWidth: 0, fill: hyColor }}
              connectNulls={false}
              isAnimationActive={false}
            />
            {/* No connecting line at all (isolated markers only) -- a point
                with an undeterminable cadence must never be guessed into
                either real line. Omitted from the legend on purpose: this
                should be rare enough on real data that a legend entry for
                it every time would just be noise. */}
            <Area
              type="monotone"
              dataKey="other"
              name="Other"
              legendType="none"
              stroke="none"
              fill="none"
              dot={makeSeriesDot('other', OTHER_COLOR, selectedDocumentId)}
              connectNulls={false}
              isAnimationActive={false}
            />
            {showForecast && (
              <Area
                type="monotone"
                dataKey="fy_forecast"
                name="Full Year (projected)"
                stroke={FORECAST_COLOR}
                strokeWidth={2}
                strokeDasharray="5 5"
                fill="url(#forecastFill)"
                dot={{ fill: FORECAST_COLOR, r: 3, strokeWidth: 0 }}
                activeDot={{ r: 4, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
            {showForecast && (
              <Area
                type="monotone"
                dataKey="hy_forecast"
                name="Half Year (projected)"
                stroke={FORECAST_COLOR}
                strokeWidth={2}
                strokeDasharray="2 4"
                fill="none"
                dot={{ fill: FORECAST_COLOR, r: 3, strokeWidth: 0 }}
                activeDot={{ r: 4, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
