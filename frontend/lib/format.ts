import * as React from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'

/**
 * Single source of truth for trend -> visual mapping across the dashboard,
 * so KpiCard (Tailwind classes) and KpiSparkline (Recharts stroke color)
 * never fall out of sync with each other.
 */
export type Trend = 'up' | 'down' | 'neutral'

/**
 * Formats a percentage change for display (e.g. `formatPercent(4.1)` -> "4.1%").
 * @param opts.showSign - when true, prefixes positive values with "+" (e.g. "+4.1%")
 */
export function formatPercent(value: number, opts?: { showSign?: boolean }): string {
  const sign = opts?.showSign && value > 0 ? '+' : ''
  return `${sign}${value}%`
}

interface TrendStyle {
  /** Tailwind text color class for the trend */
  textClass: string
  /** Tailwind background color class for the trend's pill/badge */
  bgClass: string
  /** Lucide icon representing the trend direction */
  Icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
}

/**
 * Maps a trend to its Tailwind color classes + icon. `neutral` gets its own
 * slate/dash treatment rather than falling through to the "down" (rose)
 * styling, which was the bug in the original kpi-card.tsx implementation.
 */
export function getTrendStyle(trend: Trend): TrendStyle {
  switch (trend) {
    case 'up':
      return {
        textClass: 'text-emerald-600 dark:text-emerald-400',
        bgClass: 'bg-emerald-500/10 dark:bg-emerald-500/20',
        Icon: ArrowUpRight,
      }
    case 'down':
      return {
        textClass: 'text-rose-600 dark:text-rose-400',
        bgClass: 'bg-rose-500/10 dark:bg-rose-500/20',
        Icon: ArrowDownRight,
      }
    case 'neutral':
      return {
        textClass: 'text-slate-500 dark:text-slate-400',
        bgClass: 'bg-slate-500/10 dark:bg-slate-500/20',
        Icon: Minus,
      }
  }
}

/**
 * Hex color for a trend, for direct use as a Recharts `stroke`/`fill` prop --
 * Recharts renders raw SVG and can't consume Tailwind utility classes.
 * Kept in sync with the Tailwind palette used by getTrendStyle() above
 * (emerald-500 / rose-500 / slate-500).
 */
export function getTrendColor(trend: Trend): string {
  switch (trend) {
    case 'up':
      return '#10b981' // emerald-500, matches revenue-chart.tsx's line color
    case 'down':
      return '#f43f5e' // rose-500
    case 'neutral':
      return '#64748b' // slate-500
  }
}
