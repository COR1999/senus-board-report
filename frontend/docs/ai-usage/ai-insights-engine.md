# AI Usage — feature/ai-insights-engine

## What was built

- New Next.js Route Handler `app/api/insights/route.ts` (POST): builds a
  prompt from the dashboard's current KPIs, calls OpenAI (`gpt-4o-mini`,
  JSON-mode), and returns board commentary classified as
  `positive` / `risk` / `opportunity`.
- `lib/insights.ts`: pure, tested prompt-builder and response-parser
  functions, plus `FALLBACK_INSIGHTS` (static content shown whenever OpenAI
  is unavailable, unconfigured, or returns something unparseable).
- `AiInsights` rewritten as a client component: fetches insights for the
  current `metrics` prop, shows a loading skeleton, renders each insight as
  a labeled badge (icon + text) rather than a flat numbered list.
- `frontend/.env.example` documenting `OPENAI_API_KEY` (server-side only)
  alongside the existing `NEXT_PUBLIC_API_URL`.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). Scoping was
resolved from the original project brief (which already specified OpenAI
for the frontend's AI-insights layer, separate from the backend's existing
Gemini usage for financial-document extraction) rather than needing a new
question to the user -- this was noted as an open question in the roadmap
memory from a prior session, but the brief itself already answered it.

## Notable decisions made along the way

- **OpenAI call lives in a Next.js Route Handler, not the Python backend**:
  the `openai` npm package was already a frontend dependency (unused until
  this branch), and the original brief lists OpenAI under the frontend's
  stack specifically. Keeps the key out of the client bundle without adding
  a new Python-side integration alongside the existing Gemini one.
- **Insight classification uses fixed status roles (positive/risk/opportunity),
  each always paired with an icon + text label** -- modeled on the repo's
  dataviz-skill guidance for status indicators (fixed roles, never
  color-alone) even though this isn't a literal chart; a colored badge with
  no label would have the same identifiability problem a chart would.
- **Always resolves, never throws**: both the route handler (server-side)
  and `getAiInsights()` (client-side) catch every failure mode -- missing
  key, network error, malformed JSON -- and fall back to
  `FALLBACK_INSIGHTS`. Verified by manually hitting `/api/insights` with no
  `OPENAI_API_KEY` set and confirming the fallback response.
- **`.gitignore` fix**: `frontend/.gitignore`'s blanket `.env*` rule was
  silently blocking `.env.example` (meant to be committed as documentation,
  unlike `.env.local`/`.env`). Added a `!.env.example` negation rather than
  force-adding, so the ignore rule stays correct for real env files.

## Verification performed

- `cd frontend && npx vitest run` -- 20 passed.
- `cd frontend && npx tsc --noEmit` -- no type errors.
- Started a local dev server with no `OPENAI_API_KEY` set and POSTed to
  `/api/insights` directly -- confirmed it returns `FALLBACK_INSIGHTS`
  rather than erroring.
- Did **not** verify a real OpenAI call end-to-end (would require a live
  API key and would incur real cost) -- the request-building and
  response-parsing logic are covered by unit tests instead
  (`lib/__tests__/insights.test.ts`), and the actual `chat.completions.create`
  call is a thin, standard use of the OpenAI SDK.
- No browser/screenshot tooling was available this session, so the insight
  cards' visual rendering (badge colors, icons) wasn't confirmed in a live
  browser -- covered by component tests instead.
