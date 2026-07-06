// components/dashboard/revenue-chart.tsx
'use client'

import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { type ChartDataPoint } from '@/lib/data-service'
import { projectRevenue } from '@/lib/forecast'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'

interface RevenueChartProps {
  data: ChartDataPoint[]
  /** Real reporting period for context under the title, e.g. "H1 2025". */
  periodLabel?: string | null
}

const FORECAST_PERIODS = 3

// Round-number, currency-short axis labels (e.g. "€250K") -- easier to scan
// at a glance than raw values like "250000".
function formatAxisValue(value: number): string {
  const magnitude = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (magnitude >= 1_000_000) return `${sign}€${(magnitude / 1_000_000).toFixed(1)}M`
  if (magnitude >= 1_000) return `${sign}€${Math.round(magnitude / 1_000)}K`
  return `${sign}€${magnitude}`
}

export function RevenueChart({ data, periodLabel }: RevenueChartProps) {
  const [showForecast, setShowForecast] = useState(false)

  // Combined series: real points keep their `revenue` value and get `revenue`
  // = null for forecast points (so the solid line stops there); forecast
  // points carry `forecast` instead (so the dashed line only draws there).
  // Recharts leaves a gap rather than connecting across a null value by
  // default, which is what lets the two lines visually hand off at the
  // last real data point without one overwriting the other.
  const chartData = useMemo(() => {
    if (!showForecast) return data

    const forecast = projectRevenue(data, FORECAST_PERIODS)
    if (forecast.length === 0) return data

    const lastReal = data[data.length - 1]
    return [
      ...data.map((point) => ({ ...point, forecast: null as number | null })),
      { ...lastReal, forecast: lastReal?.revenue ?? null }, // hand-off point joins the two lines
      ...forecast.map((point) => ({ period: point.period, revenue: null, forecast: point.revenue })),
    ]
  }, [data, showForecast])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Revenue Trend</CardTitle>
        {periodLabel && <CardDescription>{periodLabel}</CardDescription>}
        <CardAction>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Show forecast
            <Switch checked={showForecast} onCheckedChange={setShowForecast} />
          </label>
        </CardAction>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            {/* Horizontal-only, recessive gridlines -- "minimal gridlines, no
                chart junk" per the boardroom redesign brief. Axis lines/ticks
                dropped in favor of muted labels only. */}
            <CartesianGrid vertical={false} stroke="currentColor" className="text-foreground/10" />
            <XAxis
              dataKey="period"
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'currentColor', fontSize: 12 }}
              className="text-muted-foreground"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: 'currentColor', fontSize: 12 }}
              className="text-muted-foreground"
              tickFormatter={formatAxisValue}
              width={56}
            />
            <Tooltip />
            {/* A single series (no forecast) doesn't need a legend box -- the
                card title already names it (dataviz skill: legend only once
                there are 2+ series to distinguish). */}
            {showForecast && <Legend />}
            <Line
              type="monotone"
              dataKey="revenue"
              name="Revenue"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ fill: '#10b981', r: 4 }}
              connectNulls={false}
            />
            {showForecast && (
              <Line
                type="monotone"
                dataKey="forecast"
                name="Forecast"
                stroke="#2a78d6"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={{ fill: '#2a78d6', r: 3 }}
                connectNulls={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
