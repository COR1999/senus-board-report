import { NextResponse } from 'next/server'
import OpenAI from 'openai'
import type { Metrics } from '@/lib/data-service'
import { buildInsightsPrompt, parseInsightsResponse, FALLBACK_INSIGHTS, type Insight } from '@/lib/insights'

/**
 * POST /api/insights -- generates AI board commentary from the dashboard's
 * current KPIs. Server-side only: keeps OPENAI_API_KEY off the client.
 * Always resolves with a usable Insight[] (falls back to static content
 * rather than erroring) so the dashboard panel never breaks if OpenAI is
 * unavailable, misconfigured, or returns something unparseable.
 */
export async function POST(request: Request): Promise<NextResponse<{ insights: Insight[] }>> {
  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    return NextResponse.json({ insights: FALLBACK_INSIGHTS })
  }

  try {
    const { metrics } = (await request.json()) as { metrics: Metrics }
    const client = new OpenAI({ apiKey })

    const completion = await client.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: buildInsightsPrompt(metrics) }],
      response_format: { type: 'json_object' },
    })

    const raw = completion.choices[0]?.message?.content ?? ''
    const insights = parseInsightsResponse(raw)

    return NextResponse.json({ insights: insights ?? FALLBACK_INSIGHTS })
  } catch (error) {
    console.error('AI insights generation failed, using fallback:', error)
    return NextResponse.json({ insights: FALLBACK_INSIGHTS })
  }
}
