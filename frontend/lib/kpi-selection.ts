// lib/kpi-selection.ts
//
// Adaptive KPI selection -- the frontend half of the fallback cascade
// documented in docs/dashboard-review.md. The backend already never
// fabricates a value (a missing field is `null`/a field-specific missing-
// value message with `available: false`, never a guessed "€0" -- see
// backend/app/api/routes/metrics.py); what was missing was a layer that
// reads that signal and swaps in a different, real metric instead of
// rendering an empty/placeholder widget. Pure, framework-free functions
// (same reasoning as revenue-chart.tsx's buildChartRows) so the cascade
// logic is unit-testable without React.
import type { Metrics, MetricValue } from '@/lib/data-service'
import { formatCurrencyShort } from '@/lib/format'
import { KPI_CATEGORIES, type KpiCategory } from '@/lib/kpi-categories'

const [GROWTH_REVENUE, PROFITABILITY, CASH_LIQUIDITY, SOLVENCY_LEVERAGE, RETURNS] = KPI_CATEGORIES

export interface HeroSlot {
  key: string
  title: string
  metric: MetricValue
}

export interface SecondarySlot {
  key: string
  category: KpiCategory
  label: string
  metric: MetricValue
}

function lastReal(history: (number | null)[]): number | null {
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i] != null) return history[i] as number
  }
  return null
}

/**
 * True only for a real, present, available metric -- never throws on a
 * missing/undefined field. The frontend and backend deploy independently
 * (Vercel/Railway), so a version-skew window where the frontend briefly
 * talks to an older backend response (missing a newer field like
 * `gross_margin`) is a real, if narrow, possibility -- this cascade must
 * degrade to "not available" in that case, never crash the dashboard.
 */
function isAvailable(metric: MetricValue | null | undefined): metric is MetricValue {
  return metric != null && metric.available === true
}

/**
 * Revenue ÷ active customers -- always computable when both are real,
 * regardless of which reporting period is selected, so it resolves for
 * every real filing this project has ingested so far. The fallback your
 * own review examples name for a missing ROCE.
 */
export function revenuePerCustomerMetric(metrics: Metrics): MetricValue | null {
  if (!isAvailable(metrics.revenue) || !isAvailable(metrics.customers)) return null
  const revenue = lastReal(metrics.revenue.history)
  const customers = lastReal(metrics.customers.history)
  if (revenue == null || customers == null || customers <= 0) return null
  return {
    value: formatCurrencyShort(revenue / customers),
    change: 0,
    trend: 'neutral',
    history: [revenue / customers],
    available: true,
  }
}

/**
 * Real cash movement within the period (current − prior, both from the
 * card's own sparkline history) -- distinct from the hero row's Cash
 * Position card, which already shows the absolute balance. Used only as
 * Cash & Liquidity's fallback when Cash Runway can't be computed (no
 * disclosed operating cash-burn figure for the selected period).
 */
export function netCashMovementMetric(metrics: Metrics): MetricValue | null {
  if (!isAvailable(metrics.cash)) return null
  const real = metrics.cash.history.filter((v): v is number => v != null)
  if (real.length < 2) return null
  const current = real[real.length - 1]
  const prior = real[real.length - 2]
  const delta = current - prior
  const sign = delta > 0 ? '+' : ''
  return {
    value: `${sign}${formatCurrencyShort(delta)}`,
    change: 0,
    trend: delta > 0 ? 'up' : delta < 0 ? 'down' : 'neutral',
    history: [prior, current],
    available: true,
  }
}

/**
 * Revenue growth restated as its own stat -- the fallback for a missing
 * Bookings figure. Deliberately NOT "Customer Growth" (a fallback your own
 * review brief suggested): the schema has no `customers_prior` field at all
 * (see financial_metrics.py -- the one narrative customer count in a filing
 * is a fixed FY reference, not a period-over-period comparative pair), so
 * computing a customer growth rate today would mean fabricating a number,
 * which this project has been disciplined about never doing. Only resolves
 * when a real prior-period comparative exists (2+ real history points) --
 * otherwise Revenue's own change/trend defaults are a hardcoded 0/neutral,
 * which would misrepresent "no comparison" as "no growth".
 */
export function revenueGrowthMetric(metrics: Metrics): MetricValue | null {
  if (!isAvailable(metrics.revenue)) return null
  if (metrics.revenue.history.filter((v) => v != null).length < 2) return null
  const sign = metrics.revenue.change > 0 ? '+' : ''
  return {
    value: `${sign}${metrics.revenue.change}%`,
    change: metrics.revenue.change,
    trend: metrics.revenue.trend,
    history: metrics.revenue.history,
    available: true,
  }
}

/**
 * The 4-card hero row. Revenue/Cash/Customers are effectively always real
 * for this project's data (every ingested filing reports them), so only
 * the Profitability slot (headline "EBITDA") needs a fallback chain --
 * EBITDA is genuinely undisclosed by some filing types (e.g. the FY2025
 * Information Document, a summary-table-only prospectus). Falls through to
 * the next-best profitability signal rather than rendering a missing-value
 * sentence in giant hero type.
 */
export function selectHeroKpis(metrics: Metrics): HeroSlot[] {
  const slots: HeroSlot[] = [{ key: 'revenue', title: 'Total Revenue', metric: metrics.revenue }]

  const profitability: HeroSlot[] = [
    { key: 'ebitda', title: 'EBITDA', metric: metrics.ebitda },
    { key: 'ebitda_margin', title: 'EBITDA Margin', metric: metrics.ebitda_margin },
    { key: 'operating_margin', title: 'Operating Margin', metric: metrics.operating_margin },
    { key: 'gross_margin', title: 'Gross Margin', metric: metrics.gross_margin },
  ]
  const bestProfitability = profitability.find((c) => isAvailable(c.metric))
  if (bestProfitability) slots.push(bestProfitability)

  slots.push({ key: 'cash', title: 'Cash Position', metric: metrics.cash })
  slots.push({ key: 'customers', title: 'Active Customers', metric: metrics.customers })

  return slots
}

interface Candidate {
  key: string
  label: string
  metric: MetricValue | null
}

/**
 * The secondary "Financial Health" row -- one slot per required assignment
 * category, each with its own fallback chain (see docs/dashboard-review.md's
 * cascade table). A category is omitted entirely, never rendered empty, when
 * nothing in its chain resolves. Slots dedupe by metric key across
 * categories (e.g. Interest Cover's own fallback, EBITDA Margin, must not
 * also render under Profitability if Profitability already claimed it) so
 * the same real figure never appears twice in the same row.
 */
export function selectSecondaryKpis(metrics: Metrics): SecondarySlot[] {
  const groups: { category: KpiCategory; candidates: Candidate[] }[] = [
    {
      category: GROWTH_REVENUE,
      candidates: [
        { key: 'bookings', label: 'Bookings (new business closed)', metric: metrics.bookings },
        { key: 'revenue_growth', label: 'Revenue Growth', metric: revenueGrowthMetric(metrics) },
      ],
    },
    {
      category: PROFITABILITY,
      candidates: [
        { key: 'ebitda_margin', label: 'EBITDA Margin', metric: metrics.ebitda_margin },
        { key: 'operating_margin', label: 'Operating Margin', metric: metrics.operating_margin },
        { key: 'gross_margin', label: 'Gross Margin', metric: metrics.gross_margin },
      ],
    },
    {
      category: CASH_LIQUIDITY,
      candidates: [
        { key: 'cash_runway', label: 'Cash Runway', metric: metrics.cash_runway },
        { key: 'net_cash_movement', label: 'Net Cash Movement', metric: netCashMovementMetric(metrics) },
      ],
    },
    {
      category: SOLVENCY_LEVERAGE,
      candidates: [
        { key: 'interest_cover', label: 'Interest Cover', metric: metrics.interest_cover },
        { key: 'ebitda_margin', label: 'EBITDA Margin', metric: metrics.ebitda_margin },
        { key: 'operating_margin', label: 'Operating Margin', metric: metrics.operating_margin },
      ],
    },
    {
      category: RETURNS,
      candidates: [
        { key: 'roce', label: 'ROCE', metric: metrics.roce },
        { key: 'revenue_per_customer', label: 'Revenue per Customer', metric: revenuePerCustomerMetric(metrics) },
      ],
    },
  ]

  const used = new Set<string>()
  const slots: SecondarySlot[] = []
  for (const { category, candidates } of groups) {
    const pick = candidates.find((c) => isAvailable(c.metric) && !used.has(c.key))
    if (pick?.metric) {
      used.add(pick.key)
      slots.push({ key: pick.key, category, label: pick.label, metric: pick.metric })
    }
  }
  return slots
}
