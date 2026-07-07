// components/dashboard/revenue-chart.tsx
'use client'

import { useMemo, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { type ChartDataPoint } from '@/lib/data-service'
import { projectSeries } from '@/lib/forecast'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface RevenueChartProps {
  data: ChartDataPoint[]
  /** Real reporting period for context under the title, e.g. "Jul 2025 - Dec 2025". */
  periodLabel?: string | null
}

type MetricKey = 'revenue' | 'ebitda' | 'cash'

// Series-swap toggle, not a dual-axis overlay: Revenue/EBITDA/Cash are on
// very different scales and can have different signs (EBITDA is currently
// negative), so only one is ever plotted at a time on a single y-axis.
// Forecasting (a simple linear trendline, see lib/forecast.ts) is available
// for all three -- with only 2 real data points today the projection is a
// rough visual trend, not a real financial model, same caveat for every metric.
const METRICS: Record<MetricKey, { label: string; color: string }> = {
  revenue: { label: 'Revenue', color: '#10b981' },
  ebitda: { label: 'EBITDA', color: '#f59e0b' },
  cash: { label: 'Cash', color: '#2a78d6' },
}

const FORECAST_PERIODS = 3
const FORECAST_COLOR = '#6366f1'

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

// Round-number, currency-short axis labels (e.g. "€250K") -- easier to scan
// at a glance than raw values like "250000".
function formatAxisValue(value: number): string {
  const magnitude = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (magnitude >= 1_000_000) return `${sign}€${(magnitude / 1_000_000).toFixed(1)}M`
  if (magnitude >= 1_000) return `${sign}€${Math.round(magnitude / 1_000)}K`
  return `${sign}€${magnitude}`
}

/**
 * Custom tooltip, for three reasons the default `<Tooltip>` props couldn't
 * fix: (1) Recharts renders one row per *series*, even where that series
 * has no real value at the hovered point -- hovering the oldest real point
 * showed a "Forecast" row despite that point being pure historical Revenue.
 * Filtering to entries with a non-null value fixes that. (2) At the single
 * point where the real line hands off to the forecast line, both series
 * legitimately share the exact same value (see chartData's `withHandoff`
 * above) -- showing "Revenue: €355K" *and* "Forecast: €355K" together read
 * as a confusing duplicate, so the redundant Forecast entry is dropped
 * whenever it exactly matches a Revenue entry already shown for that same
 * point. (3) The default styling (small text, thin border) read as too
 * low-contrast/hard to see; this uses solid opaque colors, a visible
 * border, a real shadow, and bold, larger value text.
 */
function RevenueTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload) return null
  const withValue = payload.filter((entry) => entry.value !== null && entry.value !== undefined)
  // Whichever metric is the primary series (revenue/ebitda/cash -- never
  // "forecast" itself), for the same handoff-point dedup described above.
  const primaryValue = withValue.find((entry) => entry.dataKey !== 'forecast')?.value
  const entries = withValue.filter(
    (entry) => !(entry.dataKey === 'forecast' && entry.value === primaryValue)
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
            {typeof entry.value === 'number' ? formatAxisValue(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function RevenueChart({ data, periodLabel }: RevenueChartProps) {
  const [metric, setMetric] = useState<MetricKey>('revenue')
  const [showForecast, setShowForecast] = useState(false)
  const { label, color } = METRICS[metric]

  // Combined series: real points keep their selected-metric value and get
  // `forecast` = null for real points (so the solid area stops there);
  // forecast points carry `forecast` instead (so the dashed area only
  // draws there). Recharts leaves a gap rather than connecting across a
  // null value by default, which is what lets the two series visually
  // hand off at the last real data point without one overwriting the other.
  const chartData = useMemo(() => {
    if (!showForecast) return data

    const forecast = projectSeries(data, metric, FORECAST_PERIODS)
    if (forecast.length === 0) return data

    // Give the *last real point itself* a `forecast` value (rather than
    // appending a second, separate point with the same `period` label) so
    // the two series join at one shared x position -- appending a
    // duplicate entry previously made the same period label (e.g.
    // "HY2026") render twice in a row on the axis.
    const withHandoff = data.map((point, index) =>
      index === data.length - 1
        ? { ...point, forecast: point[metric] as number | null }
        : { ...point, forecast: null as number | null }
    )
    return [
      ...withHandoff,
      ...forecast.map((point) => ({
        period: point.period,
        revenue: null,
        ebitda: null,
        cash: null,
        forecast: point[metric],
      })),
    ]
  }, [data, showForecast, metric])

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
              {(Object.keys(METRICS) as MetricKey[]).map((key) => (
                <linearGradient key={key} id={`${key}Fill`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={METRICS[key].color} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={METRICS[key].color} stopOpacity={0} />
                </linearGradient>
              ))}
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
              tickFormatter={formatAxisValue}
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
            {/* A single series (no forecast) doesn't need a legend box -- the
                card title already names it (dataviz skill: legend only once
                there are 2+ series to distinguish). */}
            {showForecast && <Legend />}
            <Area
              type="monotone"
              dataKey={metric}
              name={label}
              stroke={color}
              strokeWidth={2}
              fill={`url(#${metric}Fill)`}
              dot={{ fill: color, r: 4, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 0 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            {showForecast && (
              <Area
                type="monotone"
                dataKey="forecast"
                name="Forecast"
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
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
