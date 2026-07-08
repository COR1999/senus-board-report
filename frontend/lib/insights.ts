import type { Metrics, MetricValue, ChartDataPoint } from '@/lib/data-service'
import { KPI_CATEGORIES, type KpiCategory } from '@/lib/kpi-categories'

export type InsightType = 'positive' | 'risk' | 'opportunity' | 'trend'

export interface Insight {
  text: string
  type: InsightType
  /** The concrete "so what" -- a specific recommended next step for the
   * board, distinct from the observation in `text`. */
  action: string
  /** Which of the assignment's 5 required KPI categories (see
   * lib/kpi-categories.ts) this insight is most relevant to -- omitted for
   * insights that genuinely cut across categories (e.g. headcount/customer
   * growth) rather than forced into an ill-fitting one. */
  category?: KpiCategory
}

/**
 * Shown when Gemini is unavailable (no API key, request failure, or
 * malformed response) so the panel never renders empty or broken.
 */
export const FALLBACK_INSIGHTS: Insight[] = [
  {
    text: 'Revenue growth accelerated 38% YoY, driven by enterprise adoption in UK market.',
    type: 'positive',
    action: 'Double down on the UK enterprise motion when planning next period’s sales hires.',
    category: 'Growth & Revenue',
  },
  {
    text: 'Operating expenses grew slower than revenue, improving operating margins to 18%.',
    type: 'positive',
    action: 'Maintain current cost discipline rather than loosening spend as revenue scales.',
    category: 'Profitability',
  },
  {
    text: 'Cash position supports 18+ months of operations at current burn rate.',
    type: 'opportunity',
    action: 'Runway is healthy enough to evaluate accelerating a planned hire or initiative sooner.',
    category: 'Cash & Liquidity',
  },
]

/**
 * Shown when Gemini is unavailable for the historical-trend insight
 * specifically -- a single fallback item, distinct from FALLBACK_INSIGHTS
 * (which is always 3 report-scoped items and would misrepresent what this
 * one describes if reused here).
 */
export const FALLBACK_TREND_INSIGHT: Insight = {
  text: 'Historical trend commentary is temporarily unavailable.',
  type: 'trend',
  action: '',
}

/**
 * Builds the prompt for the ONE insight describing the trajectory across
 * every report on file (not one report's own snapshot -- see
 * buildInsightsPrompt above for that). Full-Year and Half-Year points are
 * described separately and the prompt explicitly warns against blending
 * them -- the same reason the Revenue Trend chart itself renders two
 * separate lines rather than one (see docs/roadmap.md's "all-reports trend
 * chart" entry): a half-year total and a full-year total aren't directly
 * comparable magnitudes, so a naive "period-over-period" narrative across
 * both would imply a change that isn't real.
 */
export function buildHistoricalInsightPrompt(chartData: ChartDataPoint[]): string {
  const fyPoints = chartData.filter((p) => (p.cadence_months ?? 0) >= 9)
  const hyPoints = chartData.filter((p) => (p.cadence_months ?? 0) > 0 && (p.cadence_months ?? 0) <= 6)

  const describe = (points: ChartDataPoint[]) =>
    points
      .map((p) => `${p.period}: revenue ${p.revenue ?? 'N/A'}, EBITDA ${p.ebitda ?? 'N/A'}, cash ${p.cash ?? 'N/A'}`)
      .join('; ')

  return `You are a financial analyst writing board-level commentary for Senus PLC, \
a natural capital SaaS company, about its performance trajectory ACROSS every reporting \
period on file -- not just the latest one.

Full-Year periods, oldest to newest: ${fyPoints.length > 0 ? describe(fyPoints) : 'none reported yet'}.
Half-Year periods, oldest to newest: ${hyPoints.length > 0 ? describe(hyPoints) : 'none reported yet'}.

Full-Year and Half-Year figures are NOT directly comparable magnitudes (a half-year total is \
roughly half of a full year's) -- describe each cadence's own trajectory separately, never as \
one blended sequence, and never imply a period-over-period change between a Half-Year figure \
and a Full-Year figure.

Write exactly 1 short, specific insight describing the trajectory across these periods (e.g. \
accelerating or decelerating growth, a turning point, consistency vs. volatility). Provide:
- "text": the observation itself, backed by the numbers above.
- "type": always "trend" for this insight.
- "action": a distinct, concrete recommended next step for the board.

Respond with ONLY a JSON object shaped like {"insights": [{"text": string, "type": "trend", \
"action": string}]}, no surrounding prose.`
}

function isMetricValue(value: unknown): value is MetricValue {
  return typeof value === 'object' && value !== null && 'value' in value && 'trend' in value
}

/**
 * Builds the prompt sent to Gemini from the dashboard's current KPI values.
 *
 * `Metrics` mixes real KPI cards (`MetricValue`-shaped: revenue, cash, ...)
 * with plain string|null context fields (`current_period`, `prior_period`,
 * `data_extracted_at`) -- a blind `Object.entries(metrics)` previously
 * treated every one of those as a KPI too, reading `.value`/`.change`/
 * `.trend` off a plain string (producing garbage "undefined" lines in the
 * prompt) or off `null` (throwing outright, silently falling back to
 * FALLBACK_INSIGHTS via this function's caller's try/catch -- a real,
 * live-confirmed bug, not hypothetical: a genuinely new set of KPIs after
 * importing a real filing still rendered the hardcoded fallback text).
 * `isMetricValue` filters to only the real KPI entries, robust against any
 * future non-KPI field being added to `Metrics` without this needing to be
 * kept in sync with an explicit key list.
 */
export function buildInsightsPrompt(metrics: Metrics): string {
  const lines = Object.entries(metrics)
    .filter((entry): entry is [string, MetricValue] => isMetricValue(entry[1]))
    .map(([key, m]) => `- ${key}: ${m.value} (${m.change > 0 ? '+' : ''}${m.change}%, trend: ${m.trend})`)

  return `You are a financial analyst writing board-level commentary for Senus PLC, \
a natural capital SaaS company. Given these current KPIs:

${lines.join('\n')}

This dashboard already groups metrics into 5 categories: ${KPI_CATEGORIES.join(', ')}. \
It also has a Revenue Trend chart just below with a toggle between Revenue, EBITDA, \
and Cash. You can reference either (a category, or "the chart below") in your \
recommended action when it's genuinely useful, but don't force it.

Write exactly 3 short, specific insights an executive board would find useful. \
For each insight, provide:
- "text": the observation itself (what happened, backed by the numbers above).
- "type": "positive" (a clear win), "risk" (a concern worth flagging), or \
"opportunity" (something actionable to pursue).
- "action": a distinct, concrete recommended next step for the board -- the \
"so what" -- not a restatement of the observation.
- "category": whichever of [${KPI_CATEGORIES.join(', ')}] this insight is most \
relevant to, or omit this field if it genuinely doesn't fit one.

Respond with ONLY a JSON object shaped like {"insights": [{"text": string, \
"type": "positive"|"risk"|"opportunity", "action": string, "category"?: string}]}, \
no surrounding prose.`
}

function isKpiCategory(value: unknown): value is KpiCategory {
  return typeof value === 'string' && (KPI_CATEGORIES as readonly string[]).includes(value)
}

/**
 * Parses Gemini's raw response text into a validated Insight[]. Returns null
 * (rather than throwing) on anything malformed, so the caller can fall back
 * to FALLBACK_INSIGHTS -- never surface a parse error to the dashboard.
 */
export function parseInsightsResponse(raw: string): Insight[] | null {
  try {
    const parsed = JSON.parse(raw)
    const candidates: unknown[] = Array.isArray(parsed)
      ? parsed
      : Array.isArray((parsed as { insights?: unknown[] })?.insights)
        ? (parsed as { insights: unknown[] }).insights
        : []

    const insights = candidates
      .filter(
        (item): item is { text: string; type: InsightType; action?: unknown; category?: unknown } =>
          typeof item === 'object' &&
          item !== null &&
          typeof (item as Insight).text === 'string' &&
          ['positive', 'risk', 'opportunity', 'trend'].includes((item as Insight).type)
      )
      .map((item): Insight => ({
        text: item.text,
        type: item.type,
        // A model response missing/mangling this one field shouldn't sink
        // the whole insight -- render it with no action rather than falling
        // back to static content entirely.
        action: typeof item.action === 'string' ? item.action : '',
        category: isKpiCategory(item.category) ? item.category : undefined,
      }))

    return insights.length > 0 ? insights : null
  } catch {
    return null
  }
}
