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
root `README.md`'s "AI-assisted workflow" section for the working pattern itself). **37 branches**,
PRs #3–#42.

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

### Documentation, CI, and real source-document discovery (PRs #33–#39)

Wrote the README, this roadmap, and `docs/architecture.md` from empty placeholders (this project's
own graded deliverables); corrected a wrong assumption surfaced along the way — Senus had published
more than the one half-year filing already ingested — rather than quietly leaving the incorrect
claim in place; gave the deterministic-first extraction philosophy a clearer callout; and removed a
stray reference to comparing this submission against other candidates' repos that had leaked into a
doc (an internal research step, never meant to be part of the delivered repo). Added real GitHub
Actions CI for backend (pytest) and frontend (vitest/tsc/build) — its first real run caught two
genuine bugs (see "Working discipline" below). Found and downloaded the two additional real Senus
filings via the investor relations page's own JSON API (discovered by inspecting its network
requests), documenting that API's endpoints in the README. Finally, built the **investor relations
filing sync** feature itself: `GET /api/documents/external/available` and
`POST /api/documents/external/{attachment_id}/import`, approval-gated (an explicit Import button,
never silent auto-ingest) and checked on demand (page load / a manual "Check now" button, not a
background poller) — see `frontend/docs/ai-usage/investor-relations-filing-sync.md` for the full
build record, including verification performed against the real API end-to-end.

### A real production incident, and the extraction confidence service it led to (PRs #40–#42)

Immediately after PR #39 merged, importing the newly-available (non-financial) filings made the
live dashboard show "€0" everywhere. Root cause: `ReportService._save_metrics` defaulted a
genuinely missing revenue/customers/cash/ebitda to `0` instead of `None` (every other field on the
model already handled this correctly), and `/metrics/dashboard/summary` had no way to skip the
resulting all-zero row when picking "latest". **PR #40** fixed both, fixed a real JSX whitespace bug
in the new-filings banner along the way, and deleted the 6 bad documents directly from production
(with explicit confirmation, given this project's standing rule that the live Railway database isn't
a disposable local one). **PR #41** then caught the roadmap/architecture docs up to PRs #33–#39,
which a prior docs pass had missed.

That incident directly motivated **PR #42**: extracting the Information Document (the other real
filing found via the investor relations API, see PR #38) into the pipeline, plus a general-purpose
**extraction confidence service** (`backend/app/services/extraction_confidence.py`) so a repeat of
the incident is structurally impossible, not just patched for the one case that happened. Every PDF
this project processes — regardless of upload, IR import, or report regeneration — is now scored
0-100 (a transparent point system, not an invented ML probability: a value the deterministic
extractor found via a structured table match scores higher than one Gemini inferred from narrative
text, and a document matching no known financial-statement format scores 0 outright) and tiered:
`auto_accept` (≥95%, reaches the dashboard immediately), `needs_review` (85-94%, persisted and
visible via a muted "Pending Review" tag but excluded from the executive dashboard's headline KPIs
until it clears 95%), or `rejected` (<85%, nothing persisted at all). Two independent arithmetic
reconciliation checks (P&L: revenue − cost of sales = gross profit; cash flow: operating + investing
+ financing = net change in cash) cap the tier at `needs_review` even at a full point score, catching
a genuine misparse the point system alone wouldn't. A second real risk was caught and fixed in the
same branch, before it ever reached production: the Information Document's annual (12-month) figures
and the half-year filing's 6-month figures could have been silently blended into one revenue-trend
line implying regular, comparable periods — an annual total plotted next to a half-year total as
sequential same-length points reads as a fabricated ~58% revenue collapse. `/dashboard/revenue-trend`
now excludes a row only on a *confirmed* cadence mismatch (both sides' cadence known and different),
verified end-to-end against the real half-year and Information Document filings together. See
`frontend/docs/ai-usage/information-document-extraction-and-confidence-scoring.md` for the full build
record, including a genuine narrative-leakage bug found and fixed while building this (a forward-
looking "half year" mention 40+ pages from the real period statement briefly confused cadence
detection) and a real architectural finding (`ReportService.generate_report` commits a "generating"-
status row *before* the confidence check runs, so a plain rollback on rejection wasn't enough — it
had to be handled explicitly).

## Working discipline throughout Phase 2

A few rules were established early and enforced consistently across all 37 branches:

- **Never fabricate missing data.** A missing value is `null`/`None`, never a guessed `0` — this
  came up repeatedly (KPI sparkline history, reporting-period extraction, bookings figures, cadence
  detection) and was actively defended each time it resurfaced.
- **No synthetic historical data.** Two real filings are ingested as of PR #42 (the HY2026 half-year
  results and the FY2025 Information Document); every comparative on the dashboard comes from a real
  filing's own prior-period column or a genuinely separate document, never a fabricated additional
  quarter — and the two are never blended into one trend line despite their different reporting
  cadence (see the extraction confidence service entry above).
- **Verify against the real system, not just mocks.** Where practical, changes were checked against
  the actual deployed backend and production database, not just local test doubles.
- **One branch, one concern, tested before merge.** Every branch shipped with its own tests, ran
  the full suite, and was merged via its own PR rather than batched into larger, harder-to-review
  changes.

See `frontend/docs/ai-usage/` for the per-branch record of what was AI-generated vs. human-directed
and how each branch was verified.

## Next priorities (not yet started)

**Extract the ADF Farm Solutions statements — genuinely blocked, not just unscoped.** The Senus PLC
Information Document (the Euronext listing prospectus, FY2024/FY2025 annual figures) was extracted
in PR #42 — see the section above. Its sibling, **ADF Farm Solutions Consolidated Financial
Statements (30 June 2025)** (Senus's predecessor entity's full audited annual statutory accounts,
pre-re-registration as a PLC), turned out to be a **scanned PDF with no text layer at all** when
actually inspected (confirmed via PyMuPDF: `get_text()` returns nothing, every page is a single
embedded JPEG image) — the Information Document's own "SECTION 3: FINANCIAL INFORMATION" says as
much, describing it as an appended filing rather than text within the prospectus itself. This isn't
extractable by this project's text-based pipeline at all; it would need OCR or a vision-capable
model call, a genuinely separate capability from anything built so far. Deliberately left unscoped
rather than rushed.

**Hover-to-source with bounding-box highlighting.** A natural extension of the extraction confidence
work (PR #42) — clicking a KPI or flagged figure would show exactly where on the source PDF page it
was extracted from. Not built: the current extractor works on flattened text (`get_text()`), with no
page/coordinate data captured at all. Doing this properly needs a different extraction approach
(`get_text("dict")`/`get_text("words")`, which return per-word bounding boxes) plus a PDF-rendering
viewer on the frontend — a real, separate feature, not a quick add. What exists today instead: a
"View source" link on each document opens the original PDF directly (already built, PR #30).

**Other open items** (see the audit referenced in the README's "How outputs were validated"
section): PDF-download storage durability (no persistent/object storage yet), a few remaining
Documents/Reports-area gaps (bulk actions, document preview, the separate AI-generated-report PDF
export, a "Pending Review" confidence tag on the Reports table to match the one already on
Documents — same batched-query pattern, just not done in PR #42 given time), and a demo video
recording.
