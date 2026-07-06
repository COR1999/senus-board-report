'use client'

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { type SegmentValue } from '@/lib/data-service'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'

interface SegmentBreakdownProps {
  data: SegmentValue[]
}

// Validated 3-slot categorical palette (dataviz skill: blue/aqua/yellow, in
// fixed order -- see scripts/validate_palette.js). Distinct from the
// emerald/rose/slate trend colors used elsewhere, since this is identity
// (which segment), not direction (up/down).
const SEGMENT_COLORS = ['#2a78d6', '#1baf7a', '#eda100']

const formatEuro = (value: number) => `€${Math.round(value / 1000).toLocaleString()}K`

export function SegmentBreakdown({ data }: SegmentBreakdownProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Revenue by Segment</CardTitle>
        <CardDescription>Placeholder data -- segment extraction not yet available</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical" margin={{ left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tickFormatter={formatEuro} />
            <YAxis type="category" dataKey="segment" width={90} />
            <Tooltip formatter={(value) => formatEuro(Number(value))} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell key={entry.segment} fill={SEGMENT_COLORS[index % SEGMENT_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {/* Direct labels alongside the chart -- the dataviz palette check flags
            two of these three colors as sub-3:1 contrast in light mode, so
            identity must not rely on color alone. */}
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {data.map((entry, index) => (
            <span key={entry.segment} className="inline-flex items-center gap-1.5">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: SEGMENT_COLORS[index % SEGMENT_COLORS.length] }}
              />
              {entry.segment} · {entry.percentage}%
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
