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
root `README.md`'s "AI-assisted workflow" section for the working pattern itself). **46 branches**,
PRs #3–#53.

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

**PR #43** followed immediately, found entirely by actually using the live production app right
after PR #42 merged (importing the real Information Document, then watching what the dashboard did
with two real filings of different cadence present together) — a direct demonstration of why "verify
against the real system" stayed a standing rule throughout this project rather than trusting tests
alone: the *KPI cards'* own change%/history calculation still blended cadences (a "+135.9%" revenue
change comparing the new annual filing against the old half-year filing's revenue, instead of the
real +21.6% FY2025-vs-FY2024 figure), even though PR #42 had already fixed the revenue-trend chart
the same way. Also fixed in the same branch: reports showing "Document #13" instead of a real name
(a missing filename fallback on the Gemini code path), import errors showing a raw "422" instead of
the confidence gate's actual explanation (the shared `apiFetch` helper never read a FastAPI error
body's `detail` field), concurrent imports racing against each other, and a deeper bug behind "AI
Board Insights didn't update" — the insights prompt-builder crashed on the dashboard's own non-KPI
context fields (`current_period`/`prior_period`/`data_extracted_at`), silently falling back to
static placeholder text in production even for genuinely new data. See
`frontend/docs/ai-usage/mixed-cadence-kpi-comparison-and-report-naming.md` for the full record.

### A real reporting-period selector (PR #44)

Directly addresses the gap flagged in the "Next priorities" section below: once two real filings of
different cadence existed (the HY2026 half-year filing and the FY2025 Information Document, PR #42),
the dashboard could only ever show whichever one was extracted most recently — there was no way for
a board reader to deliberately pick "show me HY2026" vs. "show me FY2025." A new `GET
/metrics/dashboard/periods` endpoint lists every period eligible to appear on the dashboard (same
`auto_accept`-tier, core-metrics-present eligibility as "latest" itself), with a label combining the
bare period and its real calendar range exactly as scoped, e.g. "FY2025 (Jul 2024 – Jun 2025)". Both
`/dashboard/summary` and `/dashboard/revenue-trend` gained an optional `?document_id=` parameter that
anchors "latest" on a specific document instead of the true most recent one — selecting an older
period shows the dashboard *as it looked* for that period (that period plus its own same-cadence
history, same cadence-mismatch protection as PR #42/#43, never blended with a newer, different-
cadence filing). Omitting the parameter is byte-identical to today's behavior, verified by leaving
every pre-existing test for both endpoints unmodified. The frontend adds a `Select` next to the
existing "Data as of" banner (reusing the same shadcn/ui pattern as the Documents page's period
filter), hidden entirely when fewer than two periods exist. Verified against both real filings
end-to-end, including a real-browser screenshot check: selecting "FY2025" correctly shows €837K
revenue (+21.6%, the filing's own embedded prior-period comparative), N/A for EBITDA and every
BalanceSheetMetrics-derived ratio (genuinely undisclosed by that document type, not fabricated), and
a revenue-trend chart showing only the two real FY-cadence points — never blended with the HY2026
row. A real, previously-undiagnosed gap was found and fixed along the way: the "no eligible rows at
all" empty-dashboard branch returned `200` instead of `404` for an explicit, nonexistent
`document_id`, since the empty-check ran before the anchor-resolution logic — fixed by ordering the
check the other way, with a regression test for both orderings.

### AI Board Insights quota resilience (PR #45)

The frontend's AI Board Insights panel (a separate Gemini integration/API key from the backend's own
extraction service) had been silently returning static fallback content in production — diagnosed
back in PR #43 as *not* the prompt-builder bug found there. Revisiting it: the backend's own Gemini
integration (`backend/app/services/gemini_service.py`) already had a real circuit breaker — a 60s
backoff after a transient rate-limit error, a 24h backoff after a "prepayment credits depleted"
billing error (distinguished by message content, since the SDK doesn't expose a distinct error type),
plus proactive per-minute/per-day call caps and a response cache — but `/api/insights` had none of
this at all. Every dashboard poll that produced genuinely new metrics content kept blindly retrying
Gemini even when it was already known to be exhausted, both wasting calls that were guaranteed to
fail and never giving a recoverable per-minute/per-day quota window a chance to actually clear.
Ported the same backoff design (module-level, best-effort across a warm serverless instance — same
reasoning already used for `lib/insights-cache.ts`'s own module-level cache). Separately, that
cache itself only lived in memory, so a hard page reload wiped it and forced a fresh Gemini call for
identical data — for a single-user tool where the underlying report data changes at most a few times
a year, that's pure waste. Persisted it to `localStorage` instead, seeded once at module load and
guarded against non-browser evaluation (this module is imported by a `'use client'` component, but
Next.js still evaluates client-component modules during the server-rendering pass). If the root cause
turns out to be genuinely depleted prepayment credits rather than a recoverable rate limit, that part
still needs manual billing action at ai.studio — this fix can't conjure quota that isn't there — but
the wasted-retry problem, which is real and code-fixable, is now fixed regardless.

### "Out of scope" filings, so a rejected import stops re-appearing forever (PR #46)

A rejected external-filing import (the confidence gate scoring a governance document, e.g. an AGM
notice or Memo & Articles, below the 85% reject threshold) creates no `Document` row at all, by
design (see the extraction confidence service entry above). That meant there was previously no way
to tell "not yet reviewed" apart from "reviewed and confirmed not a financial statement" — a
non-financial filing kept re-appearing in the "new filings available" banner on every page load,
forever, with no way to dismiss it. Added a new `HiddenExternalFiling` table (its metadata
snapshotted at hide-time, not re-fetched from the IR API on every read, so a hidden entry stays
displayable even if the IR API later changes or stops listing that filing) plus three routes: `GET
/external/hidden`, `POST /external/{attachment_id}/hide`, `POST /external/{attachment_id}/unhide` —
all idempotent. `GET /external/available` now also excludes anything hidden. The Documents page gets
a small "hide" (eye-off) icon next to each available filing's Import button, and a muted "Out of
scope (N)" section below it listing anything hidden, each with a one-click "Restore" — reviewed and
dismissed filings move out of the way without disappearing for good.

### A Gemini vision backup for scanned documents (PR #48)

Unlocks the third real Senus document: ADF Farm Solutions' audited Consolidated Financial Statements
(30 June 2025), previously left deliberately out of scope as a scanned PDF with no text layer at all
(confirmed via PyMuPDF: every page is a single embedded JPEG image, `get_text()` returns nothing on
all 23 pages). Investigated free/local OCR first, per explicit direction to protect Gemini quota:
PyMuPDF has a built-in OCR hook (`get_textpage_ocr`), but it requires a real Tesseract engine
installed, and it isn't — confirmed directly (`RuntimeError: No tessdata specified and Tesseract is
not installed`). Getting that working for real would mean a system-level install on both this dev
machine and the Railway deployment (an apt/Nixpacks config change), a real infra lift for one
document. Given the explicit "not OCR tooling" direction and no viable free alternative without that
lift, the user chose a **gated, efficient Gemini vision path**: `GeminiAnalysisService.
generate_report_from_images` sends every page image in a single request (not one call per page, so a
23-page document still costs exactly one call), reusing the exact same rate-limit/backoff/cache
machinery as the text extraction path (refactored both onto one shared `_call_gemini` helper) rather
than a second, unguarded call site. Triggered only from inside the existing Import/Upload action for
a document with no text layer at all — never a background scan, and never for a document the text
pipeline could already read.

A real architectural problem surfaced while wiring this in: the existing confidence formula weights
a deterministic table match above a Gemini-narrative guess, but a scanned document has **no baseline
at all** by definition — applying the formula unchanged capped every vision extraction at 71 points
(`15+8+8` Gemini-only weights plus the 40-point format bonus), permanently below the 85% floor
regardless of accuracy. Fixed by giving vision extraction its own full-weight scoring path (there's
only one possible source, so no baseline-vs-narrative split makes sense) — but the resulting *tier*
is unconditionally capped at `needs_review`, never `auto_accept`, since there's no independent
deterministic cross-check possible for a scanned document the way there is for a text one. This
reuses the exact same "Pending Review" UI already built for the confidence gate (PR #42) — no new
frontend work needed at all. Verified via a thorough mocked test suite exercising the real 23-page
fixture end-to-end (routing, image count, confidence capping, persistence); not verified against the
live Gemini API, since this same session's earlier testing had already exhausted the account's real
quota (a billing/prepayment issue, confirmed via the actual API error), so a live attempt would just
hit the same known error rather than prove anything new.

### A new Gemini key surfaced two real bugs the mocked tests couldn't catch (PR #50)

Dropping a fresh key into Railway's `GEMINI_API_KEY` should have unblocked PR #48's vision path
immediately — instead it surfaced two genuinely separate, real bugs, both found only by actually
importing ADF Farm Solutions into production and following the failure, not by reasoning about it.

**First**: the pinned `gemini-2.0-flash` model had a real `generate_content_free_tier_requests` quota
of `limit: 0` on this specific key's project — not a billing/prepayment problem this time, just never
granted free-tier access to that pinned model at all. The frontend's `GEMINI_INSIGHTS_MODEL` had
already hit and fixed this exact failure class by defaulting to the `-latest` alias, but the backend
still defaulted to the pinned string, with only a comment warning it could happen. Tried the alias
first (matching the frontend's own fix exactly) — it hit a *different*, transient `503 UNAVAILABLE:
high demand` error against this same key. Listed the key's actually-available models directly and
confirmed `gemini-2.5-flash` (specific, current, non-preview, not an alias) works cleanly instead —
now the default in both `gemini_service.py` and `core/config.py`, still overridable via `GEMINI_MODEL`
with no redeploy if it ever needs to change again.

**Second, and more interesting**: with the model fixed, the real import *still* failed the same way —
but direct diagnosis (calling the raw Gemini client outside the app) showed the vision extraction
genuinely worked, returning real revenue/cash/EBITDA/margins. The bug was in `_generate`'s own
routing: `PDFExtractionService.extract_text()` prepends a `"--- Page N ---"` marker for *every* page
regardless of content, so a fully scanned document's `extracted_text` is never a truly empty string —
`not extracted_text.strip()` saw those markers as "real content" and silently routed the document
down the text path instead of vision, finding nothing. This slipped past every PR #48 test because
they all set `extracted_text=""` directly on a mock `Document`, never exercising what `extract_text()`
actually returns for a real scanned PDF. Fixed with a new `PDFExtractionService.has_extractable_text()`
that strips the page markers before checking for real content, plus a regression test that uses the
real `extract_text()` output specifically to close the gap that let this through the first time.

**Confirmed working against a throwaway local database**: importing ADF Farm Solutions returned
revenue €836,991 and cash €140,135 — both matching the Information Document's own figures *exactly*,
strong evidence this genuinely is the source data Senus's own summary table was built from — plus
EBITDA -€613,313, a real figure never available from any other ingested filing, correctly tagged
`needs_review` per PR #48's design. See
`frontend/docs/ai-usage/backend-gemini-model-and-empty-text-fix.md` for the full diagnostic trail.
Production itself surfaced one more real gap this local verification couldn't have caught — see the
next section.

### A production-only schema gap the local database couldn't surface (PR #51)

The user's own real import attempt, immediately after PR #50 deployed, hit a *third* bug — Postgres
this time, not Gemini: `NotNullViolationError: null value in column "customers"`. `FinancialMetrics.
customers` had been `Optional[int]` in the SQLAlchemy model for a long time, but `Base.metadata.
create_all` (this project's only schema-creation mechanism) never alters an *existing* table's column
constraints — production's `financial_metrics` table has existed since very early in the project, and
its `customers` column still carried a leftover `NOT NULL` from whenever it was first created. Every
document successfully ingested until now had happened to report a real customer count, so this never
triggered. Fixed proactively for all six of `financial_metrics`' original-release columns (`revenue`,
`customers`, `cash`, `ebitda`, `gross_margin`, `operating_margin`), not just the one that broke — none
of the other five have ever been proven NULL-safe in production either, for the same reason.
Extended the existing idempotent column-migration pattern in `database.py` with a parallel,
Postgres-only `ALTER COLUMN ... DROP NOT NULL` step (skipped entirely on SQLite, where every
test/local run already accepts these as nullable with no constraint to drop). A genuine limit of
local-only verification: SQLite never enforced this constraint the same way, so nothing short of a
real Postgres deploy could have caught it — documented honestly in
`frontend/docs/ai-usage/financial-metrics-nullable-columns.md` rather than claimed as prevented.

### Reviewing and approving a `needs_review` document (PR #52)

Importing the real ADF Farm Solutions filing (PR #48/#50) surfaced a genuine product gap: it landed
as `needs_review` (55% confidence — a scanned document with no extractable P&L text, so only cash and
a customer count came back via Gemini vision), and the Documents page could show the "Pending Review"
tag but gave no way to actually look at what was extracted or promote it onto the dashboard. Fixed
with a new `human_approved_at` timestamp column on `FinancialMetrics` — deliberately a *separate*
field from `extraction_confidence`/`extraction_confidence_tier`, so approving a document never
rewrites the algorithmic score; that stays a permanent, honest record of what the extractor actually
found, while `human_approved_at` is the independent switch that unlocks dashboard eligibility (see
`_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` in `metrics.py` and the `_effective_tier` helper in
`documents.py`, which both read it). New `POST /api/documents/{id}/approve` endpoint: 404 if the
document has no extracted metrics, 400 with a specific message if it's not actually `needs_review`
(nothing to approve), otherwise sets the timestamp and returns the document with its now-`auto_accept`
*effective* tier. Frontend: a new `DocumentReviewSheet` component (a right-side `Sheet`, reusing the
primitive already in this codebase but previously only wired up for the sidebar) triggered by a
"Review" icon button next to the existing "Pending Review" badge — shows every extracted figure
(missing ones read "Not reported", not a fabricated 0 or a blank, same convention enforced everywhere
else in this project) plus the confidence score, with an "Approve for dashboard" button. Verified
end-to-end against a real seeded document and a real running frontend/backend pair (not just the test
suite): the badge disappeared after approving, and the approved document's own figures immediately
appeared in `/dashboard/summary`.

Two reuse decisions worth recording, both a direct response to a standing instruction to check for
duplicate logic before writing new code: `useAsyncData`'s fetch hook gained an `enabled` option
(default `true`, so every existing caller is unaffected) rather than the review sheet hand-rolling its
own fetch-on-open `useState`/`useEffect` — it only fetches a document's detail while its sheet is
actually open, not for every row on the page. And revenue-chart.tsx's private `formatAxisValue`
helper (`"250000"` → `"€250K"`) was promoted to a shared, exported `formatCurrencyShort` in
`lib/format.ts` so the review sheet's own currency display uses the exact same formatting rather than
a second copy of the same magnitude-bucketing logic.

### Extending review to `rejected` documents too (PR #52, same branch)

Directly after PR #52's review-and-approve workflow shipped, a related but distinct gap was raised:
a `rejected` (<85% confidence) document was never persisted at all -- the entire `Document`/`Report`/
`FinancialMetrics` row was deleted outright the moment the confidence gate rejected it (PR #42's
original policy, from before any UI existed that could show a human *why*). That meant the only
signal a rejection ever produced was a one-time 422 error message, gone the moment the upload request
finished -- there was no way to come back later and actually see what the extractor found, or why it
scored so low.

Decided scope, deliberately narrow: **view-only**. A rejected document is now kept, with a
destructive "Rejected" tag and the same `DocumentReviewSheet` panel (in a view-only mode -- no
Approve button, since a `rejected` row is never offered an approve path at all) showing the actual
attempted values and a new `extraction_confidence_reasons` column -- the confidence score's own
point-by-point breakdown (e.g. "Revenue not found (0/30)."), which existed as data on
`ExtractionConfidence.reasons` since PR #42 but was never actually persisted anywhere before now.
Manual correction (letting a human type in the real figures by hand when automated extraction
genuinely can't parse a document) was explicitly considered and deferred -- a real, separate feature
(a third data-entry path alongside deterministic + AI extraction, with its own validation/audit-trail
questions), not a quick add to this one.

The real risk in reversing PR #42's "delete everything" policy: a `force=True` regenerate of a
document that already has *good* data must never let a worse retry overwrite it -- exactly the
incident this project has guarded against everywhere else. Fixed by threading a `persist_on_reject`
flag through `ReportService._generate` (`generate_report` passes `persist_on_reject=not force`) --
true for a first-time extraction (upload, IR import, or `generate_or_get_report`'s first call,
where nothing exists yet to protect), false for a regenerate. Locked in by three tests: a first-time
rejection actually persists (`extraction_confidence_tier="rejected"`, `Report.status="rejected"`,
reasons present), the existing regenerate-protection test extended to also assert the Report's own
status is properly restored (not left stuck), and a real vision-extraction rejection test corrected
-- its own name previously claimed "persists nothing", which was simply never actually asserted, and
would have been silently wrong the moment this branch landed if left unchecked. Also removed: two
now-redundant "delete the stuck row" cleanup blocks in `documents.py`/`reports.py`, both no longer
reachable now that `_generate` itself finalizes the row cleanly before raising.

### A second mixed-period comparison bug, found live in production (PR #53)

Directly after PR #52 deployed, using the real live app surfaced a genuine third bug in the same
family as PR #43's original mixed-cadence incident -- caught by the user asking, correctly, "why
isn't this new PDF comparing against the year prior" after approving the real ADF Farm Solutions
document into production. Two distinct root causes, confirmed against real production data before
any fix was written:

1. **A vision-extracted document's cadence was structurally unknowable.** Gemini vision only ever
   returns a free-text `reporting_period` (e.g. "Financial year ended 30 June 2025") -- unlike the
   deterministic extractor, it never derives separate `reporting_period_start`/`_end` calendar
   labels. Without those, `_cadence_months()` (metrics.py) returns `None` for any vision-extracted
   row, so PR #43's own cadence-mismatch safety filter can't protect it at all -- an unknown cadence
   is (correctly, elsewhere) never treated as a mismatch, but that same permissiveness meant it was
   never excluded from anything either. Fixed by reusing the deterministic extractor's own "ended DD
   Month YYYY" + cadence-cue parser (`FinancialMetricsExtractor._extract_period_fields`) against
   Gemini's own period string in the vision branch of `ReportService._generate` -- no new regex
   needed, since "Financial year ended 30 June 2025" is literally the same pattern the deterministic
   path already parses out of a filing's full text.
2. **Two different documents reporting the identical period were never guarded against.** Even with
   cadence fixed, ADF Farm Solutions and the Information Document are both genuine FY2025 (12-month)
   filings -- same cadence, so PR #43's filter alone doesn't catch this. `get_dashboard_metrics`
   picked "the next most recent same-cadence row" as `previous` regardless of whether it covered a
   genuinely different period, so ADF (revenue €836,991) was diffed against the Information
   Document's own *current* FY2025 figure (also €836,991 -- literally the same company/period under
   Senus's prior name) instead of the Information Document's real, embedded FY2024 comparative
   (€688,317). The result: a fabricated "0% change" that read as stagnation, on a company that had
   genuinely grown. Fixed with a new `_covers_same_period`/`_select_previous` pair in metrics.py --
   `previous` now skips any candidate row sharing the anchor's exact `reporting_period_start`/`_end`,
   falling back to the anchor's own embedded `_prior` field (honestly `N/A`/neutral here, since vision
   extraction has no `revenue_prior` of its own) rather than ever diffing against a same-period
   duplicate. Deliberately did **not** attempt to reach into a different document's `_prior` field to
   manufacture a comparison -- that would blend two independently-extracted documents' data into one
   claimed figure, contradicting the "one document's own embedded prior column" principle this project
   has held everywhere else; an honest "no comparison available" beats a plausible-looking borrowed one.

Locked in by two new tests: a vision extraction with a real "ended DD Month YYYY" period string
correctly derives `reporting_period_start`/`_end`, and a same-period-duplicate scenario correctly
falls back to neutral instead of diffing two documents against each other. Note for whoever next
touches ADF Farm Solutions in production: this fix only applies to a fresh extraction -- the
already-persisted row from before this deploy still has `reporting_period_start=None` baked in, and
Railway's ephemeral filesystem (see the README's "Known limitations") means the original PDF likely
won't survive the redeploy either, so `regenerate` won't work -- a delete + fresh re-upload is needed
to actually pick up the fix.

## Working discipline throughout Phase 2

A few rules were established early and enforced consistently across all 46 branches:

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

**Executive overview with per-category drill-down pages (idea, not built).** The current dashboard
puts all 5 of the assignment's required categories (Growth & Revenue, Profitability, Cash &
Liquidity, Solvency & Leverage, Returns — see `frontend/lib/kpi-categories.ts`, the single source of
truth for this taxonomy) on one page: a hero row for the headline metrics plus a compact stat strip
for the rest. The idea is a two-tier structure instead: the existing page stays as a genuinely
high-level executive overview, and each category gets its own drill-down page/route (e.g.
`/dashboard/cash-liquidity`) going deeper than a single card can — the ratios/inputs that feed that
category's numbers, **its own dedicated charts** (not just a sparkline — a full-size trend chart per
metric in that category, the same treatment the overview's single Revenue Trend chart gets today),
and **AI commentary scoped to that one category**
(a natural extension of `lib/insights.ts`'s existing prompt-builder, which already tags each insight
with a `KpiCategory` — the drill-down page would generate insights *for* one category specifically,
not filter the existing whole-dashboard set after the fact). Would reuse the period selector (PR #44)
directly — a category drill-down page should respect whichever period is selected on the overview,
not default back to "latest." Not yet scoped in detail (routing structure, whether drill-down pages
share the existing `getAiInsights`/`insights-cache.ts` machinery or need their own cache key per
category) — a real next feature, not started.

**Sector/competitor benchmarking in the AI insights prompt (idea, not built).** Right now
`buildInsightsPrompt` (`frontend/lib/insights.ts`) only ever gives Gemini this company's own KPI
values — an insight like "Bookings grew X%" has no external reference point for whether that's a
strong or weak result for a natural-capital SaaS company. The idea: for metrics where a genuine
comparison is meaningful (Bookings/Growth & Revenue was the example raised, though the same reasoning
would extend to any category), feed the prompt real sector or named-competitor figures alongside
Senus's own, so an insight can say something like "bookings grew X% vs. a sector median of Y%"
instead of a number in isolation. **The real blocker, consistent with this project's "never fabricate
data" rule enforced everywhere else** (see "Working discipline" above): there is currently no ingested
source of sector/competitor financial data anywhere in this pipeline — no second company's filings,
no industry-benchmark dataset. Before this is buildable, a real source would need to be found and
extracted the same way the two real Senus filings were (see PR #38's investor-relations API
discovery) — inventing plausible-sounding "sector average" numbers to make an insight sound more
authoritative would be exactly the kind of fabrication this project has actively avoided at every
other turn. Scoped here as a real idea worth pursuing once a real data source exists, not as
something to fake in the meantime.

**~~Extract the ADF Farm Solutions statements~~ — done, PRs #48/#50.** See the sections above: a
gated Gemini vision backup, used only when the deterministic text pipeline finds no text layer at
all, always capped at the `needs_review` confidence tier — confirmed genuinely working end-to-end
against the real fixture and a real key in PR #50, after finding and fixing two real bugs that had
kept it from actually working despite passing every mocked test.

**Hover-to-source with bounding-box highlighting.** A natural extension of the extraction confidence
work (PR #42) — clicking a KPI or flagged figure would show exactly where on the source PDF page it
was extracted from. Not built: the current extractor works on flattened text (`get_text()`), with no
page/coordinate data captured at all. Doing this properly needs a different extraction approach
(`get_text("dict")`/`get_text("words")`, which return per-word bounding boxes) plus a PDF-rendering
viewer on the frontend — a real, separate feature, not a quick add. What exists today instead: a
"View source" link on each document opens the original PDF directly (already built, PR #30).

**~~A real reporting-period selector~~ — done, PR #44.** See the section above. Both concrete pieces
from the original notes shipped as scoped: combined bare-label + calendar-range dropdown options, and
YoY comparisons anchored to the selected period's own same-cadence history rather than always "the
second-most-recent upload."

Deliberately **not** picking up the rest of a general executive-dashboard template (a monthly
revenue bar chart, a segment/product-line donut breakdown, budget-vs-actual variance columns) --
this project has one real filing per reporting period, not monthly-granularity data, no segment-level
revenue breakdown, and no budget figures anywhere in the source filings. Building UI for data that
doesn't exist would mean fabricating it, which this project has avoided everywhere else.

**Other open items** (see the audit referenced in the README's "How outputs were validated"
section): PDF-download storage durability (no persistent/object storage yet), a few remaining
Documents/Reports-area gaps (bulk actions, document preview, the separate AI-generated-report PDF
export, a "Pending Review" confidence tag on the Reports table to match the one already on
Documents — same batched-query pattern, just not done in PR #42 given time), and a demo video
recording. The frontend's separate AI Board Insights Gemini integration's wasted-retry problem was
fixed in PR #45 (a real circuit breaker, same design as the backend's own); if it's still returning
fallback content after that, the remaining cause is a genuine billing/quota issue needing someone
with Vercel/Google AI Studio access to check `GEMINI_INSIGHTS_API_KEY` directly — not a code fix.
