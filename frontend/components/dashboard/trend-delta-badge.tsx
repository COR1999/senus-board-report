import { cn } from '@/lib/utils'
import { getTrendStyle, type Trend } from '@/lib/format'

interface TrendDeltaBadgeProps {
  trend: Trend
  changePercentage: number
  /** 'md' matches KpiCard's pill size; 'sm' matches KpiStatStrip's more
   * compact row. @default 'md' */
  size?: 'sm' | 'md'
}

/**
 * The small colored "+12.5%"-style pill shared by KpiCard and KpiStatStrip --
 * same trend-to-color mapping as the icon badge next to it (getTrendStyle),
 * just extracted so both call sites can't drift out of sync on padding/
 * icon size the way they previously could as two independent copies.
 */
export function TrendDeltaBadge({ trend, changePercentage, size = 'md' }: TrendDeltaBadgeProps) {
  const { textClass, bgClass, Icon } = getTrendStyle(trend)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 font-semibold',
        size === 'sm' ? 'text-[11px]' : 'text-xs',
        bgClass,
        textClass
      )}
    >
      <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} strokeWidth={2.5} />
      {changePercentage}%
    </span>
  )
}
