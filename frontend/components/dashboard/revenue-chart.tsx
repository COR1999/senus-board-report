// components/dashboard/revenue-chart.tsx
'use client'

import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { type ChartDataPoint } from '@/lib/data-service'
import { projectRevenue } from '@/lib/forecast'
import { Card, CardHeader, CardTitle, CardAction, CardContent } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'

interface RevenueChartProps {
  data: ChartDataPoint[]
}

const FORECAST_PERIODS = 3

export function RevenueChart({ data }: RevenueChartProps) {
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
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="period" />
            <YAxis />
            <Tooltip />
            <Legend />
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
