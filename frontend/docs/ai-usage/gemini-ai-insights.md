# AI Usage — feature/gemini-ai-insights

## What was built

Following the OpenAI account's `insufficient_quota` billing error found in
`feature/ai-insights-auto-refresh`, the user chose to swap the AI Board
Insights panel from OpenAI to Google Gemini's free tier rather than add
billing to another paid account. Scope grew organically over the
conversation into four related pieces:

1. **Provider swap**: `app/api/insights/route.ts` now calls Gemini
   (`@google/genai`, the same SDK family as the backend's Python
   `google-genai` client) instead of OpenAI. Reads a new
   `GEMINI_INSIGHTS_API_KEY` env var -- **deliberately a separate key/project
   from the backend's own `GEMINI_API_KEY`** (financial document
   extraction), so the two features never compete for the same quota, and so
   the backend's own proactive rate limiter (which only tracks calls it
   makes itself) isn't blind to a second caller silently sharing its budget.
   `lib/insights.ts`'s comments, `.env.example`, and `AGENTS.md`'s tech-stack
   line were updated to match -- previously said "OpenAI API for AI-generated
   insights (frontend)"; both frontend and backend now use Gemini, via
   independent keys.
2. **Manual refresh button, with a spam-prevention cooldown**: a refresh
   icon button on the `AiInsights` card header (visible via `CardAction`,
   which the existing `Card` component auto-lays-out into a 2-column grid
   once a `CardAction` sibling is present) re-sends the *current* metrics to
   Gemini for a fresh analysis -- the same `getAiInsights(metrics)` call the
   automatic path uses, not a cached replay. A 30-second cooldown disables
   the button after each click: every click is a real, quota-consuming
   Gemini call, not a free UI action, so unrestricted spam-clicking would
   burn through the free-tier quota fast.
3. **Configurable model, both sides**: while verifying the swap against the
   real API, found that `gemini-2.0-flash` (hardcoded) has lost free-tier
   eligibility for new API keys (`limit: 0` in the quota error) -- confirmed
   empirically by querying the real API's model list and test-calling
   several candidates directly, not guessed. Fixed by (a) switching the
   frontend to the `gemini-flash-latest` alias, which currently resolves to
   a free-tier-eligible model, and (b) making the model itself overridable
   via env var on **both** sides (`GEMINI_INSIGHTS_MODEL` frontend,
   `GEMINI_MODEL` backend, matching the existing `GEMINI_MAX_CALLS_PER_*`
   pattern already established in `backend/app/core/config.py`) -- since a
   pinned model can lose free-tier access again with no code change on our
   side, the fix should be a config change, not a redeploy.
4. Removed the now-unused `openai` npm package.

## AI-generated vs. human-reviewed

All code written by Claude Code (Sonnet 5). The free-tier model-eligibility
issue was diagnosed by directly querying the real Gemini API (the model list
endpoint, then test-calling several candidate models), not by guessing from
training data -- the assistant's own model knowledge was explicitly
acknowledged as likely stale here (models existing well past its training
cutoff), so empirical verification against the live API stood in for it.

## Notable decisions made along the way

- **Two separate Gemini keys/projects, not one shared key**: raised
  proactively (not just accepted the user's framing) with a concrete
  technical reason beyond "good practice" -- the backend's existing
  proactive rate limiter only tracks its own call history, so a shared key
  would let the frontend's calls silently consume budget the backend
  believes is still available.
- **`gemini-flash-latest` alias over a pinned version**: chosen specifically
  *because* this session just watched a pinned version (`gemini-2.0-flash`)
  lose free-tier access. An alias trades a small amount of version-pinning
  predictability for not repeating the same failure later.
- **Model made configurable on the backend too, not just the frontend**:
  the backend's Gemini integration wasn't part of this branch's original
  scope (it currently has no practical effect on the one real filing --
  baseline extraction already covers it), but the exact same "pinned model
  can silently lose free-tier eligibility" risk applies there too, so the
  same fix was applied preemptively rather than waiting for it to break the
  same way.
- **30-second cooldown, not a stricter or looser one**: long enough to
  meaningfully block rapid spam-clicking (the actual risk being guarded
  against), short enough that a genuine "check again" a minute later doesn't
  feel broken.
- **Left `responseMimeType: 'application/json'` in the Gemini config**:
  Gemini's plain-text mode tends to wrap JSON in a markdown code fence,
  which would break `parseInsightsResponse`'s `JSON.parse` -- this native
  JSON mode avoids that without needing to strip fences client-side.

## Verification performed

- `cd frontend && npx vitest run` -- 109 passed, including 4 new
  `AiInsights` tests: manual refresh re-fetches with the current metrics,
  the cooldown disables/re-enables the button on schedule, rapid re-clicks
  during cooldown don't trigger extra calls, and -- directly answering "does
  a new upload actually produce new insights" -- a genuinely new `metrics`
  object produces genuinely different rendered insight text, replacing the
  old content rather than appending to or ignoring it.
- `cd frontend && npx tsc --noEmit` -- no errors.
- `cd frontend && npx next build` -- succeeds.
- `cd backend && ./.venv/Scripts/python.exe -m pytest tests/ -q` -- 103
  passed (unaffected; only a new configurable field + one call-site change).
- **Verified against the real Gemini API, not mocked**: after the user
  added their new free-tier key to `.env.local`, ran the actual local dev
  server and POSTed real dashboard metrics to `/api/insights`. First attempt
  returned the static fallback due to the `gemini-2.0-flash` free-tier
  eligibility issue (confirmed via the dev server's own error log, not
  assumed); after switching to `gemini-flash-latest`, a second real request
  returned genuine Gemini-generated commentary correctly reflecting the
  actual figures (e.g. correctly flagging EBITDA's 19.8% decline as a "risk"
  despite revenue growth, and cash's 915.7% increase as "positive" --
  matching the real relationships in the data, not templated text).
- Noted, not fixed (out of this branch's scope): `backend/app/core/config.py`
  also declares an `OPENAI_API_KEY` setting that nothing in the backend
  references -- dead config, found in passing while adding `GEMINI_MODEL`
  nearby.
