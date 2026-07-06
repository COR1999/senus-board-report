# AI Usage — feature/gemini-integration-fix

## What was found

The user noticed every report's `ai_commentary` field read "AI unavailable
or failed (safe fallback)" and `model_version` was `"gemini-unavailable"`,
and asked whether the Gemini integration actually works.

**Root cause: a Google AI Studio billing issue, not a code bug.** Tested
`GeminiAnalysisService` directly against the real API (with the real
`GEMINI_API_KEY` from `backend/.env`) and got:

```
429 RESOURCE_EXHAUSTED. Your prepayment credits are depleted. Please go to
AI Studio at https://ai.studio/projects to manage your project and billing.
```

The existing circuit-breaker/fallback code handled this exactly as
designed: detected the 429, disabled itself temporarily, and returned the
safe empty-fallback structure. There was nothing broken to fix in the
core logic.

**Also found**: since `feature/financial-metrics-expansion` made the
deterministic baseline extractor reliably complete (revenue/cash/ebitda/
customers all populate without needing AI enrichment) for the one real
Senus filing, `report_service._generate()` no longer even calls Gemini for
it -- `_baseline_is_complete()` short-circuits the AI call entirely
("baseline always wins the merge anyway, so calling Gemini when baseline
is already complete just burns quota for a result we'd throw away", per
the existing code comment). So this billing issue currently has **zero
practical effect** on the one real document in the system, but would
matter for any future filing the deterministic extractor can't fully
parse.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). The
investigation (running `GeminiAnalysisService` directly against the live
API to see the real error) was AI-initiated, based on the user's
observation and a recommendation to investigate before assuming a fix was
needed. The user chose, of the options presented, to have the fallback
behavior improved rather than just documented or leaving billing to be
topped up first.

## Notable decisions made along the way

- **No billing action taken** -- topping up Google AI Studio credits is
  the user's account, not something to automate or ask this agent to do.
- **One real improvement made despite the root cause being external**: the
  existing code treated every 429 identically (60s backoff), which is
  correct for a transient per-minute/per-day rate limit but wasteful for a
  depleted-credits billing problem that won't clear on its own -- every
  retry within that 60s window is guaranteed to fail again. Now
  distinguishes by checking the error message for billing-specific text
  and backs off 24h instead, avoiding repeated wasted calls against a
  quota that requires manual action to restore.
- **Didn't touch the report_service.py "skip Gemini when baseline is
  complete" logic** -- that's existing, deliberate, sensible behavior
  (documented in its own comment), not something this investigation
  suggested needed changing.

## Verification performed

- `cd backend && pytest tests/` -- 69 passed, including 4 new tests
  covering: billing-exhaustion error gets the long backoff, a plain
  rate-limit 429 gets the short backoff, a non-429 error triggers no
  backoff at all, and the safe-fallback shape is always returned on error.
- Directly exercised `GeminiAnalysisService.generate_report()` against the
  real Gemini API (not mocked) with the real configured API key, to
  observe the actual failure mode rather than guess at it.
