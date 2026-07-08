import * as React from "react"
import { cn } from "@/lib/utils"
import { getTrendStyle, getValueTextClass, type Trend } from "@/lib/format"
import { KpiSparkline } from "@/components/dashboard/kpi-sparkline"
import {
  Card,
  CardHeader,
  CardTitle,
  CardAction,
  CardContent,
} from "@/components/ui/card"

export interface KpiCardProps extends React.ComponentPropsWithoutRef<typeof Card> {
  /**
   * The title of the metric (e.g., "Total Revenue")
   */
  title: string
  /**
   * The prominent value of the metric (e.g., "€836,000")
   */
  value: string
  /**
   * The percentage change compared to the previous period (e.g., 12.5)
   */
  changePercentage: number
  /**
   * The direction of the trend (up, down, or neutral)
   */
  trend: Trend
  /**
   * A Lucide React icon component to display in the top right
   */
  icon: React.ComponentType<{ className?: string }>
  /**
   * Optional timeframe text (e.g., "vs last month", "vs target")
   * @default "vs last month"
   */
  timeframe?: string
  /**
   * Raw historical values, oldest -> newest, for an inline sparkline.
   * Omitted, empty, or single-point history renders no sparkline.
   */
  history?: (number | null)[]
  /**
   * 'hero' renders the top-of-dashboard headline metrics: bolder type (not
   * drastically larger -- oversized hero text made the page too tall to
   * view without zooming out, per direct user feedback) and a colored icon
   * badge reflecting trend. 'default' keeps the existing compact card used
   * for secondary metrics.
   * @default 'default'
   */
  variant?: 'hero' | 'default'
}

/**
 * KPI Card component for the executive dashboard.
 * Designed with a clean, high-density, professional SaaS aesthetic (inspired by Stripe/Linear).
 */
export function KpiCard({
  title,
  value,
  changePercentage,
  trend,
  icon: Icon,
  timeframe = "vs last month",
  history,
  variant = "default",
  className,
  ...props
}: KpiCardProps) {
  const { textClass, bgClass, Icon: TrendIcon } = getTrendStyle(trend)
  const isHero = variant === "hero"

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-sm border border-foreground/10",
        className
      )}
      {...props}
    >
      <CardHeader className={cn(isHero && "pb-0")}>
        <CardTitle
          className={cn(
            "text-sm font-medium text-muted-foreground tracking-tight",
            isHero && "text-xs font-semibold uppercase tracking-wider"
          )}
        >
          {title}
        </CardTitle>
        {Icon && (
          <CardAction>
            {/* Badge color follows trend (emerald/rose/slate) so the icon
                itself signals which metrics need attention, rather than
                coloring the big value number -- keeps the number itself
                high-contrast and easy to read at a glance. */}
            <div className={cn("flex h-8 w-8 items-center justify-center rounded-full transition-colors", bgClass, textClass)}>
              <Icon className="h-5 w-5" />
            </div>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className={cn("flex flex-col gap-1.5", isHero && "gap-2.5 pt-1")}>
        {/* Value color follows trend (same emerald/rose/slate palette as the
            icon badge and delta pill) -- keeps the signal visible even
            before reading the small pill text. A neutral trend (no prior-
            period comparative) falls back to checking the value's own sign,
            not a blanket default -- see getValueTextClass's own docstring. */}
        <div
          className={cn(
            "font-bold tracking-tight",
            getValueTextClass(trend, value),
            isHero ? "text-3xl sm:text-4xl" : "text-2xl sm:text-3xl"
          )}
        >
          {value}
        </div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs font-medium">
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold",
                bgClass,
                textClass
              )}
            >
              <TrendIcon className="h-3.5 w-3.5" strokeWidth={2.5} />
              {changePercentage}%
            </span>
            <span className="text-muted-foreground font-normal">{timeframe}</span>
          </div>
          {history && (
            <KpiSparkline history={history} trend={trend} className={isHero ? "h-12 w-28" : undefined} />
          )}
        </div>
      </CardContent>
    </Card>
  )
}
