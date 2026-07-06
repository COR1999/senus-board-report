'use client'

import { Line, LineChart, ResponsiveContainer } from 'recharts'
import { getTrendColor, type Trend } from '@/lib/format'
import { cn } from '@/lib/utils'

export interface KpiSparklineProps {
  /** Raw historical values, oldest -> newest. `null` entries (unreported
   * fields) are dropped before charting -- see comment below. */
  history: (number | null)[]
  /** Controls the line color via getTrendColor (emerald/rose/slate). */
  trend: Trend
  /** Tailwind size classes for the chart's container. @default 'h-10 w-24' */
  className?: string
}

/**
 * Minimal inline line chart for a KpiCard, showing a metric's recent trend
 * at a glance. Reuses the ResponsiveContainer/LineChart/monotone conventions
 * from revenue-chart.tsx but strips axes/grid/tooltip/legend for a compact,
 * decorative sparkline.
 *
 * Renders nothing (`null`) when there are fewer than 2 usable data points --
 * a single point or an empty history isn't a chart, and forcing Recharts to
 * render one anyway would just show a broken/empty box.
 */
export function KpiSparkline({ history, trend, className }: KpiSparklineProps) {
  // Drop null (missing-data) points rather than plotting them as 0 -- a small
  // decorative sparkline shouldn't fabricate a fake dip for unreported fields.
  const points = (history ?? []).filter((v): v is number => v !== null)
  if (points.length < 2) return null

  const data = points.map((value, index) => ({ index, value }))
  const color = getTrendColor(trend)

  return (
    // Recharts makes the chart surface keyboard-focusable by default
    // (its "accessibility layer"), which drew an ugly focus-ring box on
    // click -- pointless here since this is a purely decorative sparkline
    // with no independent meaning (the real value/delta are already text
    // right next to it). `accessibilityLayer={false}` below turns off the
    // tabIndex/keyboard-nav behavior that box came from; `outline-none` is
    // a belt-and-suspenders CSS fallback.
    <div className={cn(className ?? 'h-10 w-24', 'outline-none [&_svg]:outline-none')}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }} accessibilityLayer={false}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
