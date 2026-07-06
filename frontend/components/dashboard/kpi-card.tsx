import * as React from "react"
import { cn } from "@/lib/utils"
import { getTrendStyle, type Trend } from "@/lib/format"
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
  className,
  ...props
}: KpiCardProps) {
  const { textClass, bgClass, Icon: TrendIcon } = getTrendStyle(trend)

  return (
    <Card
      className={cn(
        "transition-all duration-200 hover:shadow-sm border border-foreground/10",
        className
      )}
      {...props}
    >
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground tracking-tight">
          {title}
        </CardTitle>
        {Icon && (
          <CardAction>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted/40 text-muted-foreground transition-colors group-hover/card:bg-muted">
              <Icon className="h-4 w-4" />
            </div>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        <div className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
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
              <TrendIcon className="h-3 w-3" strokeWidth={2.5} />
              {changePercentage}%
            </span>
            <span className="text-muted-foreground font-normal">{timeframe}</span>
          </div>
          {history && <KpiSparkline history={history} trend={trend} />}
        </div>
      </CardContent>
    </Card>
  )
}
