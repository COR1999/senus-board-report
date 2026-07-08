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

/**
 * Round-number, currency-short formatting (e.g. `formatCurrencyShort(250_000)`
 * -> "€250K") -- easier to scan at a glance than a raw value like "250000".
 * Shared by revenue-chart.tsx's axis/tooltip labels and the documents
 * review panel's extracted-value display, rather than each maintaining its
 * own copy of the same magnitude-bucketing logic.
 */
export function formatCurrencyShort(value: number): string {
  const magnitude = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (magnitude >= 1_000_000) return `${sign}€${(magnitude / 1_000_000).toFixed(1)}M`
  if (magnitude >= 1_000) return `${sign}€${Math.round(magnitude / 1_000)}K`
  return `${sign}€${magnitude}`
}

/** Formats a byte count as a readable size (e.g. `formatFileSize(245_000)` -> "239 KB"). */
export function formatFileSize(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes >= 1_000_000) return `${(bytes / 1_048_576).toFixed(1)} MB`
  if (bytes >= 1_000) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
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
 * The color a KPI's big value number should render in -- distinct from
 * `getTrendStyle(trend).textClass` alone, which a real production screenshot
 * showed reading wrong: EBITDA at -€613K rendered in plain neutral/black
 * text because its `trend` was `'neutral'` (no prior-period comparative to
 * diff against, the "no data" case, not "genuinely unchanged") -- the
 * *value itself* being deeply negative was never considered, only whether
 * it had moved. When a real trend exists (up/down), that's the strongest
 * signal and wins, exactly as before. When trend is neutral, this instead
 * checks whether the formatted value itself is negative (backend currency/
 * percent formatters always prefix a negative value with "-" before the
 * symbol, e.g. "-€613K"/"-73.3%" -- never "€-613K" -- so a leading "-" is a
 * reliable signal) and renders it in the same rose/"down" color used
 * elsewhere for a genuine decline, since a negative EBITDA or margin is
 * inherently a warning signal regardless of whether it improved or worsened.
 * A neutral, non-negative value (e.g. a flat customer count) still renders
 * in the plain default color -- nothing alarming about that case.
 */
export function getValueTextClass(trend: Trend, value: string): string {
  if (trend !== 'neutral') return getTrendStyle(trend).textClass
  return value.trim().startsWith('-') ? getTrendStyle('down').textClass : 'text-foreground'
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
