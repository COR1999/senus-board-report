import type { Metrics } from '@/lib/data-service'
import { KPI_CATEGORIES, type KpiCategory } from '@/lib/kpi-categories'

export type InsightType = 'positive' | 'risk' | 'opportunity'

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

/** Builds the prompt sent to Gemini from the dashboard's current KPI values. */
export function buildInsightsPrompt(metrics: Metrics): string {
  const lines = Object.entries(metrics).map(
    ([key, m]) => `- ${key}: ${m.value} (${m.change > 0 ? '+' : ''}${m.change}%, trend: ${m.trend})`
  )

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
          ['positive', 'risk', 'opportunity'].includes((item as Insight).type)
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
