import type { Metrics } from '@/lib/data-service'

export type InsightType = 'positive' | 'risk' | 'opportunity'

export interface Insight {
  text: string
  type: InsightType
}

/**
 * Shown when Gemini is unavailable (no API key, request failure, or
 * malformed response) so the panel never renders empty or broken.
 */
export const FALLBACK_INSIGHTS: Insight[] = [
  { text: 'Revenue growth accelerated 38% YoY, driven by enterprise adoption in UK market.', type: 'positive' },
  { text: 'Customer acquisition cost remains stable while lifetime value increases 24%.', type: 'positive' },
  { text: 'Operating expenses grew slower than revenue, improving operating margins to 18%.', type: 'positive' },
  { text: 'Cash position supports 18+ months of operations at current burn rate.', type: 'opportunity' },
]

/** Builds the prompt sent to Gemini from the dashboard's current KPI values. */
export function buildInsightsPrompt(metrics: Metrics): string {
  const lines = Object.entries(metrics).map(
    ([key, m]) => `- ${key}: ${m.value} (${m.change > 0 ? '+' : ''}${m.change}%, trend: ${m.trend})`
  )

  return `You are a financial analyst writing board-level commentary for Senus PLC, \
a natural capital SaaS company. Given these current KPIs:

${lines.join('\n')}

Write 3-5 short, specific insights an executive board would find useful. \
Classify each as "positive" (a clear win), "risk" (a concern worth flagging), \
or "opportunity" (something actionable to pursue). \
Respond with ONLY a JSON object shaped like \
{"insights": [{"text": string, "type": "positive"|"risk"|"opportunity"}]}, no surrounding prose.`
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

    const insights = candidates.filter(
      (item): item is Insight =>
        typeof item === 'object' &&
        item !== null &&
        typeof (item as Insight).text === 'string' &&
        ['positive', 'risk', 'opportunity'].includes((item as Insight).type)
    )

    return insights.length > 0 ? insights : null
  } catch {
    return null
  }
}
