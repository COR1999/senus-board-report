import { cn } from '@/lib/utils'
import { getTrendStyle, type Trend } from '@/lib/format'
import { Card, CardContent } from '@/components/ui/card'
import type { KpiCategory } from '@/lib/kpi-categories'

export interface StatStripItem {
  key: string
  /** Short category label shown above the metric name, e.g. "Profitability". */
  category: KpiCategory
  label: string
  value: string
  changePercentage: number
  trend: Trend
  /** Whether a real prior-period value backs `changePercentage` -- e.g.
   * Bookings has no prior-period comparative at all, so its change is
   * always a hardcoded 0/neutral. Showing "0%" next to that reads as a
   * real (if unremarkable) delta rather than "no comparison exists" --
   * the badge is only rendered when this is true. */
  hasComparison: boolean
}

interface KpiStatStripProps {
  items: StatStripItem[]
  /** Shared real-date context (e.g. "Jul 2025 - Dec 2025"), shown once
   * above the row since every item with a real prior comparative shares
   * the same current period -- avoids repeating it 5 times. */
  periodLabel?: string
}

/**
 * Secondary-metrics row -- one card per stat (not one shared card) so the
 * assignment-required categories (Profitability, Cash & Liquidity, Solvency
 * & Leverage, Returns) plus Bookings each read as a distinct, uncluttered
 * box rather than columns competing inside a single card.
 */
export function KpiStatStrip({ items, periodLabel }: KpiStatStripProps) {
  return (
    <div>
      {periodLabel && (
        <p className="mb-2 text-sm text-muted-foreground">{periodLabel}</p>
      )}
      {/* Single column on phone -- 5 items in 2 columns leaves an orphaned
          cell on the last row and cramps the category/label/value stack. */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {items.map(({ key, category, label, value, changePercentage, trend, hasComparison }) => {
          const { textClass, bgClass, Icon: TrendIcon } = getTrendStyle(trend)
          return (
            <Card key={key} className="border-foreground/10">
              <CardContent className="flex flex-col gap-1">
                {/* Was text-[11px] font-medium text-muted-foreground/70 -- both
                    the tiny size and the extra opacity reduction on top of an
                    already-muted color made this caption hard to read. */}
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {category}
                </span>
                <span className="text-sm font-medium text-foreground/80">{label}</span>
                <div className="flex items-baseline gap-2">
                  {/* Same trend-follows-value-color treatment as KpiCard --
                      a metric like EBITDA Margin at -133.5% shouldn't read in
                      plain neutral text. */}
                  <span
                    className={cn(
                      'text-xl font-semibold tracking-tight',
                      trend === 'neutral' ? 'text-foreground' : textClass
                    )}
                  >
                    {value}
                  </span>
                  {hasComparison && (
                    <span
                      className={cn(
                        'inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold',
                        bgClass,
                        textClass
                      )}
                    >
                      <TrendIcon className="h-3 w-3" strokeWidth={2.5} />
                      {changePercentage}%
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
