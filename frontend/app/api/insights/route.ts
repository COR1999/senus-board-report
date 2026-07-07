import { NextResponse } from 'next/server'
import { GoogleGenAI } from '@google/genai'
import type { Metrics } from '@/lib/data-service'
import { buildInsightsPrompt, parseInsightsResponse, FALLBACK_INSIGHTS, type Insight } from '@/lib/insights'

// Overridable via env var, not hardcoded -- verified directly against the
// real API that a pinned version (e.g. "gemini-2.0-flash") can lose
// free-tier quota eligibility for a given key with no warning, while the
// "latest" alias below currently still resolves to a free-tier-eligible
// model. Google can (and did, during this same debugging session) change
// which specific model a key has free access to; an env var means that's
// a config change, not a redeploy.
const MODEL = process.env.GEMINI_INSIGHTS_MODEL || 'gemini-flash-latest'

/**
 * POST /api/insights -- generates AI board commentary from the dashboard's
 * current KPIs. Server-side only: keeps GEMINI_INSIGHTS_API_KEY off the
 * client. Always resolves with a usable Insight[] (falls back to static
 * content rather than erroring) so the dashboard panel never breaks if
 * Gemini is unavailable, misconfigured, or returns something unparseable.
 *
 * Deliberately a *separate* API key/project from the backend's own Gemini
 * integration (financial document extraction --
 * backend/app/services/gemini_service.py). Sharing a key would put this
 * route's calls in the same quota pool the backend's own rate limiter
 * tracks for itself, silently defeating that tracking.
 */
export async function POST(request: Request): Promise<NextResponse<{ insights: Insight[] }>> {
  const apiKey = process.env.GEMINI_INSIGHTS_API_KEY
  if (!apiKey) {
    return NextResponse.json({ insights: FALLBACK_INSIGHTS })
  }

  try {
    const { metrics } = (await request.json()) as { metrics: Metrics }
    const client = new GoogleGenAI({ apiKey })

    const response = await client.models.generateContent({
      model: MODEL,
      contents: buildInsightsPrompt(metrics),
      config: {
        temperature: 0.3,
        // Gemini otherwise tends to wrap JSON in a ```json fenced block in
        // plain-text mode, which breaks parseInsightsResponse's JSON.parse.
        responseMimeType: 'application/json',
      },
    })

    const insights = parseInsightsResponse(response.text ?? '')

    return NextResponse.json({ insights: insights ?? FALLBACK_INSIGHTS })
  } catch (error) {
    console.error('AI insights generation failed, using fallback:', error)
    return NextResponse.json({ insights: FALLBACK_INSIGHTS })
  }
}
