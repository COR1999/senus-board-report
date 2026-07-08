# Project Roadmap & Build History

This project was built in two distinct phases: an initial foundation built manually, then an
extended feature-development phase using **Claude Code** to streamline implementation once that
foundation was in place. This document records both phases as they actually happened, in order.

## Phase 1 — Manual foundation (2 – 6 July 2026, little AI assistance)

The project structure, core services, and initial dashboard shell were organized and implemented
directly, with minimal AI assistance. This phase established:

- **Project scaffolding** — the full-stack repo structure (`backend/`, `frontend/`), initial
  gitignore/tooling setup, and Railway/deployment groundwork.
- **Backend foundation** — FastAPI app initialized with models, schemas, and routes; async
  SQLAlchemy + PostgreSQL wiring; connection pooling for Railway.
- **PDF extraction pipeline** — `pdf_service.py` (PyMuPDF text extraction) and the first version of
  `financial_metrics_extractor.py`, iterated on directly to fix narrative-leakage and parsing bugs.
- **AI-powered reports system** — `gemini_service.py` (Gemini client, quota-safe report generation,
  typed responses) and `report_service.py` (orchestrating extraction + AI enrichment), including an
  early migration from OpenAI to `google.genai`.
- **Dashboard shell** — the initial `DashboardContainer`, KPI cards, revenue chart, AI insights
  panel, reports table, sidebar, and top nav, wired to a `data-service.ts` layer with mock-data
  fallback.
- **Cleanup passes** — removing an unused `app/database` package, fixing a broken pytest suite,
  fixing `requirements.txt` encoding, adding sparkline history to the dashboard summary endpoint.

By the end of this phase (PR #1 `feature/reports-summary`, PR #2 `feature/pipeline_service`), the
app had a working end-to-end pipeline: upload a PDF → extract metrics → generate an AI-enriched
report → render it on a dashboard. **46 commits**, 2 July – 6 July 2026.

## Phase 2 — Claude Code–assisted development (6 – 8 July 2026)

From this point on, development was streamlined using **Claude Code (Sonnet 5)**, working one
feature/fix branch at a time with an explicit plan-then-implement-then-verify discipline (see the
root `README.md`'s "AI-assisted workflow" section for the working pattern itself). **27 branches**,
PRs #3–#32.

### KPI system & financial metrics (PRs #3–#9, #13)

Typed KPI summary endpoint with sparkline history, revenue analytics with forecasting, the AI
Board Insights panel wired to OpenAI (later Gemini), reports module with CSV export, dashboard
layout shell (`/reports`, `/documents`, `/settings` pages), a typed API client + hooks layer, and
the assignment-critical **Cash & Liquidity / Solvency & Leverage / Returns** metric categories
(reprioritized ahead of schedule once the full assignment brief was shared mid-session) plus
Bookings extraction from the filing's own narrative text.

### Executive redesign & polish (PRs #10, #11, #12, #15, #16)

A CORS hotfix for the deployed frontend; delete-document and regenerate-report actions; a
diagnosis of Gemini extraction failures (a billing/quota issue, not a code bug); and the
**boardroom-aesthetic redesign** — consolidating KPI cards into a hero row + compact stat strip,
adding real reporting-period extraction (replacing a placeholder "vs last quarter" claim), and
fixing a revenue-trend chart bug live-caught by the user testing on their phone. Followed by a
Reports/Documents/Settings polish pass (real theme toggle, dark-mode fixes, table padding/spacing
fixes from direct user feedback screenshots).

### Data integrity fixes (PRs #19, #24, #28)

Content-hash duplicate-upload detection; a real calendar-month period range ("Jul 2025 – Dec 2025")
replacing the ambiguous bare "HY2026" label; and detecting filing cadence (half-year vs. full-year)
from the document's own language rather than assuming half-year, so a future full-year upload
doesn't silently compute a wrong period.

### AI insights refinement (PRs #20, #21, #22, #23, #25)

Migrated the AI Board Insights panel from OpenAI to Gemini after a billing exhaustion; extracted
shared `CURRENT_USER`/`ErrorBanner` utilities; added background polling with content-based dedup;
gave each insight a recommended board action and category tag; then fixed a real bug where
navigating away from the dashboard and back (e.g. to Settings) reset an in-memory guard and
triggered a wasted, non-deterministic re-generation — replaced with a content-keyed cache that
survives remounts.

### UI polish & single-user tidy-up (PRs #26, #27, #29)

A full pass on user-reported UI issues: separated the secondary KPI row into individual cards,
fixed AI Insights text alignment, bumped icon sizes, replaced a sidebar that couldn't collapse with
an icon-only rail that expands on hover, removed a redundant AI Insights subheading, renamed
forecast labels for clarity, and fixed a segmented-control tab whose "active" state was invisible
(traced to two design tokens sharing the same color value). Then, per explicit product direction
that this is a **single-user boardroom presentation tool, not a multi-tenant product**, removed the
notifications bell and user dropdown menu (half of it was dead, non-functional UI) in favor of a
plain presenter-identity display.

### Final feature work & cleanup (PRs #30, #31, #32)

Download support for uploaded PDFs (with an honest error message when Railway's ephemeral storage
has already lost an older file — confirmed empirically against the real deployed document); a real
period filter on Reports/Documents (replacing a disabled stub) and a 20MB upload size limit; and a
backend code-quality pass fixing an N+1 query and an over-fetching response in the document list
endpoint.

## Working discipline throughout Phase 2

A few rules were established early and enforced consistently across all 27 branches:

- **Never fabricate missing data.** A missing value is `null`/`None`, never a guessed `0` — this
  came up repeatedly (KPI sparkline history, reporting-period extraction, bookings figures, cadence
  detection) and was actively defended each time it resurfaced.
- **No synthetic historical data.** Senus's one real filing is genuinely its first-ever public
  results — there is nothing earlier to compare against, so every comparative on the dashboard comes
  from that filing's own prior-period column, never a fabricated additional quarter.
- **Verify against the real system, not just mocks.** Where practical, changes were checked against
  the actual deployed backend and production database, not just local test doubles.
- **One branch, one concern, tested before merge.** Every branch shipped with its own tests, ran
  the full suite, and was merged via its own PR rather than batched into larger, harder-to-review
  changes.

See `frontend/docs/ai-usage/` for the per-branch record of what was AI-generated vs. human-directed
and how each branch was verified.
