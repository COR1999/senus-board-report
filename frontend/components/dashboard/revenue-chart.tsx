'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const data = [
  { month: 'Jan', revenue: 60000, customers: 85 },
  { month: 'Feb', revenue: 75000, customers: 95 },
  { month: 'Mar', revenue: 95000, customers: 108 },
  { month: 'Apr', revenue: 110000, customers: 118 },
  { month: 'May', revenue: 132000, customers: 125 },
  { month: 'Jun', revenue: 158000, customers: 132 },
  { month: 'Jul', revenue: 185000, customers: 138 },
  { month: 'Aug', revenue: 215000, customers: 145 },
  { month: 'Sep', revenue: 245000, customers: 150 },
  { month: 'Oct', revenue: 280000, customers: 155 },
  { month: 'Nov', revenue: 520000, customers: 157 },
  { month: 'Dec', revenue: 836991, customers: 158 },
]

export function RevenueChart() {
  return (
    <Card className="col-span-full">
      <CardHeader>
        <CardTitle>Revenue Trend</CardTitle>
        <CardDescription>Monthly revenue over the past year</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="month"
              stroke="hsl(var(--muted-foreground))"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              style={{ fontSize: '12px' }}
              tickFormatter={(value) => `€${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
              formatter={(value) => [`€${(value as number).toLocaleString()}`, 'Revenue']}
            />
            <Line
              type="monotone"
              dataKey="revenue"
              stroke="hsl(16 92% 66%)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}