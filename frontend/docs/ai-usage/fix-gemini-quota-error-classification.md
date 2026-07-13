# AI Usage — fix/gemini-quota-error-classification

## Context

Found while manually driving the app end-to-end in a local, isolated demo run (fresh SQLite DB,
real upload pipeline, live dashboard in a browser) ahead of the user's presentation. The dashboard's
"AI Board Insights → Historical trend" panel showed "Historical trend commentary is temporarily
unavailable" instead of a generated insight. Tracing it to the frontend dev server's own log showed
the real Gemini API error: an ordinary `RESOURCE_EXHAUSTED` 429 for the free-tier daily request cap
(`generate_content_free_tier_requests`, limit 20) -- but the app's circuit breaker had disabled
Gemini for 24 hours instead of the usual 60 seconds, as if it were a billing outage.

## What was found and fixed

Both `frontend/app/api/insights/route.ts` (`backoffForError`, added in `fix/ai-insights-quota-
resilience`) and `backend/app/services/gemini_service.py` (`_call_gemini`'s exception handler, added
in `feature/gemini-integration-fix`) distinguish a transient rate-limit 429 (60s backoff) from a
genuine billing/prepayment-exhausted 429 (24h backoff) by checking the error message for
billing-specific text. Both used a bare substring/regex match on the word **"billing"** for the
24h case.

The bug: Google's own boilerplate text for an ordinary quota 429 --
`"...please check your plan and billing details..."` -- also contains that substring. So a routine,
recoverable-in-a-minute daily-quota bump was misclassified as a billing outage and got the 24h
backoff instead, live-confirmed from the frontend server log during this session.

The fix, in both files: only the specific `"prepayment credits are depleted"` phrase (the actual
wording Google uses for a real billing/prepayment problem, and the only wording ever confirmed
against the real API for that case) triggers the 24h backoff. Every other `429`/`RESOURCE_EXHAUSTED`
-- including one whose own boilerplate happens to mention "billing details" -- gets the normal 60s
backoff.

## What this can't fix

If the underlying daily quota is genuinely still exhausted, no code change grants more of it --
Gemini calls will keep failing with the same 429 until Google's own quota window resets or the key's
plan changes. What's fixed is purely the self-inflicted extra downtime: the app no longer takes an
ordinary, already-clearing quota bump and turns it into a guaranteed 24-hour outage of its own
making.

## Verification performed

- `cd backend && pytest tests/` -- 245 passed, including 1 new regression test
  (`test_ordinary_quota_429_mentioning_billing_boilerplate_still_uses_short_backoff`) using the
  real captured error message shape, asserting the short backoff is used despite the "billing details"
  boilerplate.
- `cd frontend && npx vitest run` -- 237 passed, including 1 new regression test in
  `app/api/insights/__tests__/route.test.ts` with the same real error shape, asserting Gemini is
  retried after 60s (not still backed off at 24h).
- `cd frontend && npx tsc --noEmit` -- clean.
