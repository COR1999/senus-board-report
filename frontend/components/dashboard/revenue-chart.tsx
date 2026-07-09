// components/dashboard/revenue-chart.tsx
'use client'

import { useMemo, useState } from 'react'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { type ChartDataPoint } from '@/lib/data-service'
import { projectSeries } from '@/lib/forecast'
import { formatCurrencyShort } from '@/lib/format'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
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

// Display label per cadence bucket -- shared by the chart legend/tooltip
// (via METRICS' own naming below) and the point-count-aware render modes,
// so a "1 real point" stat card and a "2 real point" bar both read as
// "Full Year" / "Half Year" the same way the 3+-point line chart already does.
const BUCKET_LABELS: Record<CadenceBucket, string> = { fy: 'Full Year', hy: 'Half Year', other: 'Other' }

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

export type ChartRenderMode = 'empty' | 'stat' | 'bars' | 'line'

/**
 * Chart presentation follows how many real points actually exist per
 * cadence bucket, not habit -- see docs/dashboard-review.md's "Fixing the
 * charts" section. A line/area chart around 1-2 real dots is chart-junk
 * dressed up as a trend that isn't there; a single stat callout or a
 * side-by-side bar comparison communicates the same real numbers more
 * honestly. Uses the MAX count across buckets (not each bucket
 * independently) -- once any cadence has a real 3+-point trend, the
 * existing line/area treatment already handles a thinner sibling bucket
 * correctly (an isolated 1-2-point marker, exactly as it does today), so
 * there's no need to split rendering per-bucket and recombine two chart
 * types in one canvas.
 */
export function determineRenderMode(data: ChartDataPoint[]): ChartRenderMode {
  const counts: Record<CadenceBucket, number> = { fy: 0, hy: 0, other: 0 }
  for (const point of data) counts[cadenceBucket(point.cadence_months)]++
  const max = Math.max(counts.fy, counts.hy, counts.other)
  if (max === 0) return 'empty'
  if (max === 1) return 'stat'
  if (max === 2) return 'bars'
  return 'line'
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

  // Point-count-aware presentation -- see determineRenderMode's own
  // docstring and docs/dashboard-review.md's "Fixing the charts" section.
  // A cadence bucket with only 1-2 real points doesn't get a line chart
  // (a 1-2-dot "trend" communicates nothing); it gets a stat callout or a
  // bar comparison instead.
  const renderMode = useMemo(() => determineRenderMode(data), [data])

  // Forecasting (Method One, a linear trend) is only ever offered once a
  // real 3+-point trend exists to project from -- same gate as renderMode
  // itself, so the toggle (hidden below outside 'line' mode) can never
  // silently produce nothing the way it could before this existed.
  const forecastActive = showForecast && renderMode === 'line'

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
    () => buildChartRows(data, metric, forecastActive),
    [data, forecastActive, metric]
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
      </CardHeader>
      {/* A plain flex row below the header, not CardHeader's own `1fr auto`
          CSS grid `CardAction` slot -- that grid's `auto` column sizes to
          its content's max-content width regardless of `flex-wrap` on the
          child, so on a narrow viewport the 3-button switcher + forecast
          toggle would overflow the card and get clipped by its
          `overflow-hidden` instead of wrapping. A normal block-level flex
          row wraps correctly under real width constraints. */}
      <div className="flex flex-wrap items-center gap-4 px-(--card-spacing)">
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
        {/* Only offered once a real 3+-point trend exists to project from
            (see renderMode/forecastActive above) -- with 1-2 real points,
            a trend-based forecast has nothing reliable to fit a line
            through and would previously toggle on and silently render
            nothing. */}
        {renderMode === 'line' && (
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Show forecast
            <Switch checked={showForecast} onCheckedChange={setShowForecast} />
          </label>
        )}
      </div>
      <CardContent>
        {renderMode === 'empty' && (
          <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
            No {label.toLowerCase()} data yet -- upload a report to see this chart.
          </div>
        )}

        {/* Exactly one real point per cadence bucket -- a single stat
            callout per bucket communicates the real number honestly,
            instead of a line chart with nothing to draw a line between. */}
        {renderMode === 'stat' && (
          <div className="grid gap-4 sm:grid-cols-2">
            {(['fy', 'hy', 'other'] as CadenceBucket[])
              .map((bucket) => ({
                bucket,
                point: data.find((p) => cadenceBucket(p.cadence_months) === bucket),
              }))
              .filter((b): b is { bucket: CadenceBucket; point: ChartDataPoint } => b.point != null)
              .map(({ bucket, point }) => {
                const bucketColor = bucket === 'hy' ? hyColor : bucket === 'fy' ? color : OTHER_COLOR
                const value = point[metric]
                return (
                  <div key={bucket} className="rounded-lg border border-foreground/10 p-4">
                    <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      {BUCKET_LABELS[bucket]}
                    </div>
                    <div className="mt-1 text-2xl font-bold tracking-tight" style={{ color: bucketColor }}>
                      {value != null ? formatCurrencyShort(value) : 'Not reported'}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {point.period} · only report on file for this cadence
                    </div>
                  </div>
                )
              })}
          </div>
        )}

        {/* Exactly two real points in the fullest cadence bucket -- a
            side-by-side bar comparison (current vs. prior), not a
            two-dot line implying a trend. */}
        {renderMode === 'bars' && (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} accessibilityLayer={false} margin={{ left: 4, right: 12, top: 8 }}>
              <CartesianGrid vertical={false} stroke="currentColor" className="text-foreground/10" />
              <XAxis
                dataKey="period"
                axisLine={false}
                tickLine={false}
                tickMargin={10}
                tick={{ fill: 'currentColor', fontSize: 12 }}
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
              <Tooltip offset={24} content={(props) => <RevenueTooltip {...props} />} />
              <Legend />
              <Bar dataKey="fy" name="Full Year" fill={color} radius={[4, 4, 0, 0]} maxBarSize={64} />
              <Bar dataKey="hy" name="Half Year" fill={hyColor} radius={[4, 4, 0, 0]} maxBarSize={64} />
              <Bar dataKey="other" name="Other" legendType="none" fill={OTHER_COLOR} radius={[4, 4, 0, 0]} maxBarSize={64} />
            </BarChart>
          </ResponsiveContainer>
        )}

        {renderMode === 'line' && (
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
            {forecastActive && (
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
            {forecastActive && (
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
        )}
      </CardContent>
    </Card>
  )
}
