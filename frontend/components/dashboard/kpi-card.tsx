import * as React from "react"
import { ArrowUpRight, ArrowDownRight } from "lucide-react"
import { cn } from "@/lib/utils"
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
   * The direction of the trend (up or down)
   */
  trend: "up" | "down"
  /**
   * A Lucide React icon component to display in the top right
   */
  icon: React.ComponentType<{ className?: string }>
  /**
   * Optional timeframe text (e.g., "vs last month", "vs target")
   * @default "vs last month"
   */
  timeframe?: string
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
  className,
  ...props
}: KpiCardProps) {
  const isUp = trend === "up"

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
        <div className="flex items-center gap-1.5 text-xs font-medium">
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold",
              isUp
                ? "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400"
                : "bg-rose-500/10 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400"
            )}
          >
            {isUp ? (
              <ArrowUpRight className="h-3 w-3" strokeWidth={2.5} />
            ) : (
              <ArrowDownRight className="h-3 w-3" strokeWidth={2.5} />
            )}
            {changePercentage}%
          </span>
          <span className="text-muted-foreground font-normal">{timeframe}</span>
        </div>
      </CardContent>
    </Card>
  )
}
