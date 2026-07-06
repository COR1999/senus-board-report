import { cn } from '@/lib/utils'
import { getTrendStyle, type Trend } from '@/lib/format'
import { Card, CardContent, CardHeader, CardDescription } from '@/components/ui/card'

export interface StatStripItem {
  key: string
  /** Short category label shown above the metric name, e.g. "Profitability". */
  category: string
  label: string
  value: string
  changePercentage: number
  trend: Trend
}

interface KpiStatStripProps {
  items: StatStripItem[]
  /** Shared real-date context (e.g. "H1 2024 vs H1 2025"), shown once for
   * the whole strip since every item with a real prior comparative shares
   * the same current/prior period -- avoids repeating it 5 times. */
  periodLabel?: string
}

/**
 * Compact, sparkline-free secondary-metrics band -- one shared Card, not five
 * separate KpiCards, so the assignment-required categories (Profitability,
 * Cash & Liquidity, Solvency & Leverage, Returns) plus Bookings stay fully
 * visible without competing with the hero row for visual weight. Each stat
 * keeps its own small category caption so the graded categories stay
 * identifiable even at this reduced size.
 */
export function KpiStatStrip({ items, periodLabel }: KpiStatStripProps) {
  return (
    <Card>
      {periodLabel && (
        <CardHeader>
          <CardDescription>{periodLabel}</CardDescription>
        </CardHeader>
      )}
      {/* Single column on phone -- 5 items in 2 columns leaves an orphaned
          cell on the last row and cramps the category/label/value stack. */}
      <CardContent className="grid grid-cols-1 gap-6 sm:grid-cols-3 lg:grid-cols-5">
        {items.map(({ key, category, label, value, changePercentage, trend }) => {
          const { textClass, bgClass, Icon: TrendIcon } = getTrendStyle(trend)
          return (
            <div key={key} className="flex flex-col gap-1">
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
                <span
                  className={cn(
                    'inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold',
                    bgClass,
                    textClass
                  )}
                >
                  <TrendIcon className="h-2.5 w-2.5" strokeWidth={2.5} />
                  {changePercentage}%
                </span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
