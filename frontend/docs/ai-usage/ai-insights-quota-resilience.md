# AI Usage — fix/ai-insights-quota-resilience

## Context

User request: find a way to stop the AI Board Insights panel from hitting the Gemini quota, since
this had already been diagnosed (PR #43) as silently falling back to static content in production.

## What was found and fixed

Compared the frontend's Gemini integration (`frontend/app/api/insights/route.ts`) against the
backend's own (`backend/app/services/gemini_service.py`), which already has a real circuit breaker:
a 60s backoff after a transient rate-limit (429) error, a 24h backoff after a "prepayment credits
depleted" billing error (distinguished by message content, since the SDK doesn't expose a distinct
error type for the two), plus proactive per-minute/per-day call caps and a response cache. The
frontend route had **none** of this — every dashboard poll producing genuinely new metrics content
would blindly retry Gemini, even seconds after it had already failed with the exact same error. Two
real, code-level improvements:

1. **Ported the backend's backoff design to `/api/insights`** — module-level `disabledUntil`
   timestamp, same two backoff durations, same error-message-based distinction between a transient
   rate limit and a billing/prepayment issue. Best-effort (a serverless cold start resets it, same
   caveat the backend doesn't have since it's a persistent process) but strictly better than retrying
   blind on every request.
2. **Persisted `lib/insights-cache.ts`'s content-hash cache to `localStorage`.** It was previously
   module-scope-only, which meant a hard page reload wiped it and forced a fresh Gemini call for
   identical data — pure waste for a single-user tool where the underlying report data changes at
   most a few times a year. Seeded once at module load, guarded against non-browser evaluation (this
   module is imported by a `'use client'` component, but Next.js still evaluates client-component
   modules during the server-rendering pass).

## What this can't fix

If the root cause is genuinely depleted prepayment credits (a billing problem, not a rate limit — the
backend hit exactly this during this same session, see its own log: "Your prepayment credits are
depleted. Please go to AI Studio..."), no code change can conjure quota that isn't there. That still
needs manual action at ai.studio. What's fixed is the *wasted-retry* problem: the route no longer
keeps hammering an already-known-exhausted quota on every request, which both wastes calls that are
guaranteed to fail and prevents a genuinely recoverable rate limit from ever getting a quiet window to
clear.

## Verification performed

- `npx vitest run` — 144 passed (6 new: 4 for the route's backoff behavior — no call without an API
  key, a successful call, skipping Gemini within the 60s rate-limit backoff window then retrying
  after it clears, and staying backed off for the full 24h billing-exhausted window rather than the
  short one — and 2 for `localStorage` persistence surviving a simulated page reload).
- `npx tsc --noEmit` and `npx next build` — both clean.
