'use client'

import type { ReactNode } from 'react'
import { Info, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { formatCurrencyShort } from '@/lib/format'
import { summarizeGuidanceForecast, latestRevenueBaseline, SENUS_GROWTH_GUIDANCE } from '@/lib/forecast'
import type { ChartDataPoint } from '@/lib/data-service'

interface GrowthForecastCardsProps {
  /** Same all-reports chart data the Revenue Trend chart renders -- this
   * card projects forward from the most recent REAL revenue point in it. */
  chartData: ChartDataPoint[]
  /** Applied to the root Card only when it actually renders (never on the
   * `null` no-baseline path) -- lets a caller (Presentation Mode) target
   * this section without that id ever existing in the DOM when there's
   * genuinely nothing here to show. Optional: every other caller is
   * unaffected. */
  sectionId?: string
}

/** One of the four indigo stat tiles below -- extracted since all four
 * shared identical wrapper/label/value markup, differing only in content
 * and whether a progress bar follows. */
function ForecastStatTile({
  label,
  value,
  children,
}: {
  label: string
  value: string
  children?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight text-indigo-600 dark:text-indigo-400">{value}</div>
      {children}
    </div>
  )
}

/**
 * Method Two forecasting (see lib/forecast.ts) as a set of standalone
 * stat cards, rather than another chart -- per docs/dashboard-review.md's
 * "Forecast, redesigned" section, a Projected Revenue / CAGR / Growth
 * Multiple / Progress-to-Target readout is often more informative than a
 * single trend line, especially while real historical data is still thin
 * (today: two reporting periods, of two different cadences). Renders
 * nothing at all when there's no real revenue baseline to project from --
 * never a placeholder implying a forecast exists when it doesn't.
 */
export function GrowthForecastCards({ chartData, sectionId }: GrowthForecastCardsProps) {
  const baseline = latestRevenueBaseline(chartData)
  const summary = baseline ? summarizeGuidanceForecast(baseline.revenue, baseline.year) : null

  if (!baseline || !summary) return null

  const progress = Math.min(100, Math.max(0, summary.progressToTargetPercent))

  return (
    // The highlight id lives on this plain wrapper, not the Card itself --
    // Card's own base styling already includes `ring-1 ring-foreground/10`
    // and `overflow-hidden` (see components/ui/card.tsx), both of which
    // fight a highlight ring added directly to it (competing ring classes
    // at equal specificity, and overflow-hidden can clip an outline/ring
    // painted at the element's own edge). Confirmed directly: the ring
    // never appeared here despite the exact same class-add mechanism
    // working on every OTHER step's plain-div wrapper. A wrapper with no
    // competing styles of its own sidesteps both problems.
    <div id={sectionId} className="scroll-mt-24 rounded-2xl">
      <Card className="border-indigo-500/20">
      <CardHeader>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          <CardTitle>Growth to {summary.targetYear}</CardTitle>
          <Tooltip>
            <TooltipTrigger aria-label="Forecast methodology" className="text-muted-foreground">
              <Info className="h-4 w-4" />
            </TooltipTrigger>
            <TooltipContent>
              Forecast based on published {SENUS_GROWTH_GUIDANCE.label}, projected forward from{' '}
              {baseline.year}&apos;s revenue of {formatCurrencyShort(baseline.revenue)} -- not a historical
              trend line.
            </TooltipContent>
          </Tooltip>
        </div>
        <CardDescription>
          Projected from {baseline.year} revenue at a minimum {summary.cagrPercent.toFixed(0)}% CAGR, per
          Senus&apos;s own published growth strategy.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <ForecastStatTile label={`Projected Revenue ${summary.targetYear}`} value={formatCurrencyShort(summary.projectedTarget)} />
          <ForecastStatTile label="Target CAGR" value={`${summary.cagrPercent.toFixed(0)}%`} />
          <ForecastStatTile label="Growth Multiple" value={`${summary.growthMultiple.toFixed(1)}×`} />
          <ForecastStatTile label="Progress to Target" value={`${summary.progressToTargetPercent.toFixed(0)}%`}>
            <div
              className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-indigo-500/15"
              role="progressbar"
              aria-valuenow={Math.round(progress)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Progress toward ${summary.targetYear} revenue target`}
            >
              <div className="h-full rounded-full bg-indigo-500" style={{ width: `${progress}%` }} />
            </div>
          </ForecastStatTile>
        </div>
      </CardContent>
      </Card>
    </div>
  )
}
