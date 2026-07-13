import { NextResponse } from 'next/server'
import { GoogleGenAI } from '@google/genai'
import type { Metrics, ChartDataPoint } from '@/lib/data-service'
import {
  buildInsightsPrompt,
  buildHistoricalInsightPrompt,
  parseInsightsResponse,
  FALLBACK_INSIGHTS,
  FALLBACK_TREND_INSIGHT,
  type Insight,
} from '@/lib/insights'

// Overridable via env var, not hardcoded -- verified directly against the
// real API that a pinned version (e.g. "gemini-2.0-flash") can lose
// free-tier quota eligibility for a given key with no warning, while the
// "latest" alias below currently still resolves to a free-tier-eligible
// model. Google can (and did, during this same debugging session) change
// which specific model a key has free access to; an env var means that's
// a config change, not a redeploy.
const MODEL = process.env.GEMINI_INSIGHTS_MODEL || 'gemini-flash-latest'

// A 429 can mean two very different things: a transient per-minute/per-day
// rate limit (clears on its own -- a short backoff is right), or the Google
// AI Studio project's prepayment credits being depleted (a billing problem
// that requires manual action and will NOT clear on its own -- retrying
// every request just wastes calls hitting the same exhausted quota until
// someone tops up billing). Same distinction, same backoff durations, as
// the backend's own circuit breaker (backend/app/services/gemini_service.py)
// -- this route previously had no equivalent at all, so every dashboard
// poll that produced genuinely new metrics kept blindly retrying Gemini
// even when it was already known to be exhausted, both wasting calls and
// never giving a recoverable per-minute/per-day quota a chance to clear.
const RATE_LIMIT_BACKOFF_MS = 60_000
const BILLING_EXHAUSTED_BACKOFF_MS = 24 * 60 * 60 * 1000

// Module-level, not per-request -- same reasoning as the old localStorage
// insights cache: a serverless function instance can be reused ("warm")
// across multiple invocations, and this state should persist across those,
// not reset every request. Best-effort only (a cold start resets it, and
// multiple concurrent instances don't share it) -- strictly better than no
// circuit breaker at all, not a guarantee. Shared across both the per-report
// and historical-trend insight modes below -- they're the same Gemini
// key/project, so a quota exhaustion from one must back off the other too.
let disabledUntil = 0

function isGeminiAvailable(): boolean {
  return Date.now() >= disabledUntil
}

function disableGeminiTemporarily(ms: number): void {
  disabledUntil = Date.now() + ms
}

function backoffForError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)
  // Only the specific "prepayment credits are depleted" phrasing indicates
  // a real billing outage. A bare `/billing/i.test(message)` used to also
  // match here -- but a routine RESOURCE_EXHAUSTED quota message's own
  // boilerplate ("please check your plan and billing details") contains
  // that substring too, so an ordinary free-tier daily-cap 429 was
  // misclassified as a billing outage and given a 24h backoff instead of
  // the intended 60s one (confirmed directly against the real API: a
  // `generate_content_free_tier_requests` quota response has no
  // "prepayment credits" phrase at all).
  if (message.includes('prepayment credits are depleted')) {
    console.error(
      'Gemini API prepayment credits are depleted -- this needs manual billing action at ' +
        'https://ai.studio/projects, not a transient rate limit. Backing off ' +
        `${BILLING_EXHAUSTED_BACKOFF_MS / 1000}s instead of the usual ` +
        `${RATE_LIMIT_BACKOFF_MS / 1000}s so we don't keep re-hitting a quota that won't recover on its own.`
    )
    disableGeminiTemporarily(BILLING_EXHAUSTED_BACKOFF_MS)
  } else if (message.includes('429') || message.includes('RESOURCE_EXHAUSTED')) {
    disableGeminiTemporarily(RATE_LIMIT_BACKOFF_MS)
  }
}

type InsightsRequestBody = { metrics: Metrics } | { chartData: ChartDataPoint[] }

function isTrendRequest(body: InsightsRequestBody): body is { chartData: ChartDataPoint[] } {
  return 'chartData' in body
}

/**
 * POST /api/insights -- generates AI board commentary. Server-side only:
 * keeps GEMINI_INSIGHTS_API_KEY off the client. Always resolves with a
 * usable Insight[] (falls back to static content rather than erroring) so
 * the dashboard panel never breaks if Gemini is unavailable, misconfigured,
 * or returns something unparseable.
 *
 * Two modes, selected by which key the request body carries:
 * - `{ metrics }` -- the existing per-report flow (exactly 3 insights about
 *   the current period's own KPIs, see buildInsightsPrompt).
 * - `{ chartData }` -- the historical-trend flow (exactly 1 insight
 *   describing the trajectory across every report on file, see
 *   buildHistoricalInsightPrompt). Kept on this same route rather than a
 *   separate one specifically so both modes share the one circuit breaker
 *   above -- they're the same Gemini key/quota pool, so a route split would
 *   need to duplicate (and keep in sync) the backoff state instead.
 *
 * `isFallback` distinguishes a real generation from the static placeholder
 * content -- a real, live-confirmed gap this used not to signal at all: a
 * caller that caches results must never cache fallback content identically
 * to a real success, or refresh stays permanently disabled ("already up to
 * date") even though nothing real had ever been generated for that data.
 *
 * Deliberately a *separate* API key/project from the backend's own Gemini
 * integration (financial document extraction --
 * backend/app/services/gemini_service.py). Sharing a key would put this
 * route's calls in the same quota pool the backend's own rate limiter
 * tracks for itself, silently defeating that tracking.
 */
export async function POST(
  request: Request
): Promise<NextResponse<{ insights: Insight[]; isFallback: boolean; model: string | null }>> {
  const apiKey = process.env.GEMINI_INSIGHTS_API_KEY

  let body: InsightsRequestBody
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ insights: FALLBACK_INSIGHTS, isFallback: true, model: null })
  }

  const trendMode = isTrendRequest(body)
  const fallback = trendMode ? [FALLBACK_TREND_INSIGHT] : FALLBACK_INSIGHTS

  if (!apiKey || !isGeminiAvailable()) {
    return NextResponse.json({ insights: fallback, isFallback: true, model: null })
  }

  try {
    const client = new GoogleGenAI({ apiKey })
    const prompt = isTrendRequest(body) ? buildHistoricalInsightPrompt(body.chartData) : buildInsightsPrompt(body.metrics)

    const response = await client.models.generateContent({
      model: MODEL,
      contents: prompt,
      config: {
        temperature: 0.3,
        // Gemini otherwise tends to wrap JSON in a ```json fenced block in
        // plain-text mode, which breaks parseInsightsResponse's JSON.parse.
        responseMimeType: 'application/json',
      },
    })

    const insights = parseInsightsResponse(response.text ?? '')

    if (insights === null) {
      return NextResponse.json({ insights: fallback, isFallback: true, model: null })
    }
    return NextResponse.json({ insights, isFallback: false, model: MODEL })
  } catch (error) {
    console.error('AI insights generation failed, using fallback:', error)
    backoffForError(error)
    return NextResponse.json({ insights: fallback, isFallback: true, model: null })
  }
}

// Test-only: module-level state persists across tests in the same file
// (vitest doesn't reset modules between `it()` blocks by default).
export function _resetGeminiBackoffForTests(): void {
  disabledUntil = 0
}
