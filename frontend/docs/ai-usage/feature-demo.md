# AI Usage — feature/demo

## Context

User request: a live, guided walkthrough of the app for the actual graded presentation, that steps
through the dashboard, the extraction/confidence pipeline, and the reports archive with real data —
not a static slide deck, not screenshots. Explicit requirements added as the branch progressed: never
show empty charts or the frontend's static mock-data fallback live on stage; showcase the
extraction/confidence pipeline and the period-merge feature specifically; run entirely isolated from
production (a fresh local database, never the real Railway Postgres instance); be launchable with a
single double-click; leave the user with discussion material for the interviewers, grounded in real
project history rather than generic talking points.

## What was built

- **`components/presentation/`** — `PresentationProvider`/`usePresentation` (cross-page tour state,
  mounted once at the root layout so it survives client-side navigation), `PresentationOverlay` (the
  floating step panel), `PresentationTrigger` (the "Present" button, dashboard-only).
- **`lib/presentation/steps.ts`** — the ordered step list spanning `/`, `/documents`, `/reports`,
  including two steps whose `demoUploads` live-upload real filings through the actual upload endpoint.
- **`backend/scripts/local_demo_server.py`** / **`local_demo_seed.py`** — a local-only backend
  launcher (registers the SQLite/JSONB compiler shim `tests/conftest.py` already uses, since
  `app/main.py`'s real startup path has none) and a pre-seed script.
- **`scripts/local-demo/run.ps1`** / **`run.sh`** / **`stop.ps1`**, plus **`Start Demo.bat`** /
  **`Stop Demo.bat`** at the repo root — a self-cleaning, one-command (or one-double-click) launcher.
- **`docs/presentation-talking-points.md`** — deeper discussion material for the live presentation,
  pulled from this project's actual commit history.

## Design decisions, in the order they were actually made

**Isolation first.** The very first requirement was that this must never touch the real Railway
Postgres database. `DATABASE_URL`/`NEXT_PUBLIC_API_URL` are overridden only as process-level
environment variables for the two processes the launcher scripts themselves start — `backend/.env`
and `frontend/.env.local` (the real credentials) are never read or written by any of this. Verified
directly, not just assumed: `backend/local_demo.db` was inspected before and after every session-long
test run to confirm it stayed a genuinely separate SQLite file.

**Pre-seed a reliable baseline, live-upload the risky demonstration.** The original design pre-seeded
the vision-extracted ADF filing and live-uploaded the two reliable ones. Direct user feedback reversed
this after watching it fail live: "make sure when I'm presenting I'm not showing false data or empty
charts." Gemini vision's reliability on ADF had already been observed to vary call-to-call within this
same session, and — critically — the Cost Waterfall chart structurally can *never* populate from a
vision extraction at all (`cost_of_sales`/`administrative_expenses` are only ever populated by the
deterministic extractor, confirmed directly from `report_service.py`'s `_save_balance_sheet_metrics`).
Redesigned around a reliable, deterministically-extracted baseline (the HY2026 half-year PR) pre-seeded
before the tour starts, with the two riskier filings uploaded live and purely additive — if their merge
doesn't land on a given run, the dashboard was already showing real, complete data the whole time.

**Exactly 3 files, 2 periods, one merge.** An explicit user constraint once the design above was in
place: not 4 files, not an accidental duplicate — 3 filings uploaded in total, 2 of them merging into
1 period, so exactly 2 real periods end up on the dashboard. The mock/synthetic FY2026 filing (clearly
labeled "not a real Senus PLC filing" in its own header) was deliberately excluded from the live
demo's file set entirely, given this is a graded academic submission — presenting fabricated financial
data as real, even briefly, wasn't worth the risk regardless of how clearly it's labeled in the PDF
itself.

**Talking points, not a script.** First pass used an "Ask me: ..." imperative framing running to two
sentences each. Direct feedback: "not too pushy," "smaller sentences." Rewritten to one short question
each (5-8 words), no command framing — the icon next to it already signals what it is. A separate
request ("bring attention to the approve and merge... make some good talking points... so we can have
a discussion with the interviewers") led to `docs/presentation-talking-points.md`: a broader reference
pulled from `git log` and this project's own `docs/roadmap.md`, organized by theme (data integrity, AI
reliability, period reconciliation, confidence gating, schema evolution without a migration tool,
engineering process), each with a real incident and a discussion question — not written from scratch,
compiled from what had already genuinely happened in this project's history.

## Real bugs found and fixed while building and rehearsing this

None of these were hypothetical — each was found by actually running the app end-to-end (mostly via
the user's own live rehearsal, a few via this session's own automated/manual verification) and traced
to a real cause before being fixed:

1. **Gemini vision's `reporting_period` field had no formatting guidance**, so it came back in
   inconsistent phrasing the deterministic period parser couldn't read — blocking the live merge from
   ever triggering. Fixed by asking for an exact, regex-matchable phrasing in the prompt itself
   (`gemini_service.py`); confirmed working via a direct, non-mocked call against the real API.
2. **Gemini vision responses are cached by file hash for 24h**, so "retrying" the same file against
   the same running backend process returns the identical cached result — three consecutive manual
   retries during this session's own debugging turned out to be one real call plus two cache hits.
   Corrected `local_demo_seed.py`'s retry logic (and its own doc comments) to reflect this rather than
   loop pointlessly.
3. **A transient Gemini `503` was treated as a hard failure.** Confirmed directly that the identical
   request succeeds on an immediate retry — added exactly one retry in `_call_gemini`, specifically for
   503/UNAVAILABLE, never for 429/quota (which the existing backoff already handles correctly).
4. **The Reports archive kept a superseded document's report visible as an unexplained duplicate**
   after a merge (e.g. "ADF Farm Solutions Limited" appearing twice) — `ReportService.list_reports()`
   now excludes superseded rows from the "list everything" case, confirmed not to affect the
   single-document lookup case used elsewhere.
5. **A failed historical-trend generation displayed its own static fallback text as if it were a real
   insight.** Inconsistent with every other adaptive section of this dashboard, which renders nothing
   rather than a placeholder — `useHistoricalTrendInsight` now leaves the insight unset on a fallback.
6. **A highlight ring added directly to `GrowthForecastCards`' `Card` never rendered**, because `Card`
   already carries its own `ring-1`/`overflow-hidden` base styling that fights a second ring on the
   same element — moved the highlight target to a plain wrapper, the same pattern already used by
   every other step.
7. **The floating step panel could be positioned partly off-screen**, cutting off the Next/Back
   controls with no way to advance, once a step's actual rendered height exceeded a hardcoded
   estimate (or changed after a React-driven layout shift, e.g. a table gaining a row, which fires
   neither a scroll nor a resize event). Fixed with the panel's own measured height, a hard viewport
   clamp, a pinned footer, and continuous polling rather than relying only on scroll/resize listeners.
8. **The period-selector row's right-alignment broke** when the "Present" button was first added
   directly into its flex container — restored by grouping the button with the selector as a single
   right-aligned unit, matching production's existing layout.

## AI-generated vs. human-reviewed

All code on this branch was written by Claude Code (Sonnet 5). Nearly every fix above was initiated by
direct, specific user feedback from live rehearsal (screenshots, exact error text, "this doesn't make
sense given what's on screen") rather than independent AI-driven QA — the AI's role was diagnosing
root cause quickly (e.g. tracing the caching behavior, the `Card` ring conflict, the `_save_balance_
sheet_metrics` vision/deterministic split) and fixing it, then verifying against the real running app
rather than assuming the fix worked. The exceptions were self-initiated: the pre-seed-vs-live-upload
redesign was proposed with reasoning, not requested outright, and the final full-tour verification (see
below) was run without being asked, specifically to catch further issues before handing back again
after several rounds of live-testing friction.

## Verification performed

- `cd backend && pytest tests/` — 248 passed, including new regression tests for: the 503 retry (exactly
  one retry, never looped; a genuine success case), the reports-list superseded-document exclusion
  (both the "list everything" and single-document-lookup cases), and the existing quota-misclassification
  test from the companion `fix/gemini-quota-error-classification` branch.
- `cd frontend && npx vitest run` — 254 passed, including 16 new tests across
  `components/presentation/__tests__/` (start/next/prev/stop navigation and highlighting, keyboard
  shortcuts, the existence filter for a genuinely-absent target, demo-upload-once-per-step with a
  processing state, Next/Back ignored mid-upload) and a new historical-trend-fallback regression test.
- `npx tsc --noEmit` and `npx next build` — both clean.
- **A full, automated, non-mocked walkthrough of the real ten-step tour**, driven via a headless
  browser against a freshly seeded local instance (fresh `local_demo.db`, real backend, real frontend,
  real Gemini calls) — every step's Next/Back button confirmed reachable, including the ~64-second live
  upload/merge step, ending cleanly at "Finish." Run specifically to independently confirm the overlay
  positioning fix before asking the user to re-test yet again, after several earlier rounds where a fix
  believed complete turned out not to be once actually exercised live.
