# Senus Board Report

An AI-native board reporting platform: upload a company's financial filing (PDF), and it extracts
structured financial metrics, computes the ratios a board actually asks about, and presents them as
an executive dashboard with AI-generated commentary.

Built as a graduate technical assessment for **Assiduous Corp**. The case-study company is
**Senus PLC**, a real Irish natural-capital/MRV SaaS company admitted to Euronext Access Dublin on
22 December 2025 — the dashboard is populated from its real public filings (half-year results and
its Euronext listing prospectus), not synthetic data.

**Live app:** https://senus-board-report.vercel.app
**API:** https://senus-board-report-production.up.railway.app
**Demo video:** _TODO — not yet recorded_

---

## The brief

> Using the historic financial information available [on the Senus investor relations site],
> design and build an AI-native platform that prepares a Board Report for Management, the Board,
> Equity Investors and Credit Providers... Focus on AI methods for extracting financial information
> from the source documents into a database powering a model that underpins the Board Report
> application.

Required metric categories: **Growth & Revenue** (YoY, MoM, Customers, Channels, Bookings),
**Profitability** (Gross/Operating/EBITDA margin), **Cash & Liquidity** (cash runway, working
capital), **Solvency & Leverage**, **Returns** (ROCE), plus AI-generated commentary. All five are
implemented and visible on the dashboard (see `backend/docs/metrics-expansion-plan.md`).

## Investor relations API

Senus's investor relations page is a client-rendered SPA (`app.assiduous.tech/investor-relations/senus`)
backed by a plain JSON REST API — undocumented, but discoverable by inspecting the page's network
requests. Useful for anyone extending this project (see `docs/roadmap.md`'s "Next priorities"):

| Endpoint | Returns |
|---|---|
| `GET https://api.app.assiduous.tech/v1/investor-relations/senus/documents/all-documents` | Information-Document-category filings (metadata: `attachmentId`, `fileName`, `fileSize`, `labels`, `publishedDate`) |
| `GET https://api.app.assiduous.tech/v1/investor-relations/senus/reports/all-documents` | Results filings (the half-year results PDF this project already ingests) |
| `GET https://api.app.assiduous.tech/v1/investor-relations/senus/corporate/all-documents` | Corporate presentations |
| `GET https://api.app.assiduous.tech/v1/investor-relations/senus/regulatory/all-documents` | Regulatory news/press releases |
| `GET https://api.app.assiduous.tech/v1/investor-relations/senus/documents/documents/{attachmentId}` | The actual PDF for a given `attachmentId` from any of the above lists |

Every document currently in `backend/docs/source-documents/` was fetched via this last endpoint.

This project also wraps that API with two of its own endpoints so new filings can be pulled in
without a manual download/re-upload round-trip: `GET /api/documents/external/available` lists
filings not yet in this system (matched against already-ingested documents by both
`attachmentId` and filename — some filings appear under more than one `attachmentId` across
categories), and `POST /api/documents/external/{attachmentId}/import` downloads and runs one
through the same extraction pipeline as a manual upload. Checked on page load / a manual
"Check now" button on the Documents page — not polled in the background — and always
approval-gated: importing is a deliberate click, never automatic.

## Architecture

```
 PDF upload                Deterministic extractor         Postgres
┌───────────┐   raw bytes  ┌──────────────────────┐  rows  ┌─────────────┐
│  Next.js  │─────────────▶│   FastAPI backend     │───────▶│ FinancialMet │
│ (Vercel)  │◀─────────────│   (Railway)           │◀───────│ rics, Report │
└───────────┘   REST JSON  └──────────┬───────────┘  reads │ Document     │
      │                               │                     └─────────────┘
      │ direct call                   │ fallback/enrichment
      ▼ (server-side key)             ▼ (only when the deterministic
┌───────────┐                  ┌─────────────┐        extractor is incomplete)
│  Gemini   │                  │   Gemini     │
│ (insights)│                  │ (extraction) │
└───────────┘                  └─────────────┘
```

**Extraction philosophy — deterministic first, LLM as a fallback, not the primary reader.** Senus's
filings are native-text PDFs, not scans — so `financial_metrics_extractor.py` parses them directly
with a context-aware regex engine (it isolates the P&L/Balance Sheet/Cash Flow sections *before*
parsing, specifically to prevent narrative leakage — e.g. "EBITDA positive by FY2028" in a
forward-looking statement must never be misread as a real EBITDA figure). Gemini only runs to fill
gaps the deterministic pass couldn't find. This is a deliberate choice, not a default: a reliable
regex/table parse over real extractable text is more reproducible and auditable than routing every
figure through a vision model — the LLM is reserved for genuine gaps and narrative commentary, not
asked to re-derive numbers a parser can already get right.

This philosophy extends numerically, not just architecturally: `extraction_confidence.py` scores
every processed document (0-100, weighted so a deterministic table match counts for more than an
LLM guess at the same field) before its data is trusted. A document that doesn't match a known
financial-statement format at all — or where the deterministic baseline contributed nothing — scores
too low to ever reach the dashboard; a value found only via Gemini narrative inference is treated as
less certain than one read directly from a table. Two independent arithmetic reconciliation checks
(does revenue − cost of sales equal gross profit; does the cash flow statement's components sum to
the stated net change) catch a genuine misparse the presence-only checks wouldn't. Built directly in
response to a real incident — see `docs/roadmap.md`.

- **Frontend** (`frontend/`): Next.js App Router dashboard. Fetches from the FastAPI backend on a
  60-second poll (metrics, chart data, reports), each independently content-deduped so an unchanged
  poll never triggers a re-render or a wasted downstream AI call.
- **Backend** (`backend/`): FastAPI + async SQLAlchemy. See the extraction philosophy above —
  Gemini only runs when the deterministic pass is incomplete.
- **AI Board Insights** (frontend-only, `app/api/insights/route.ts`): a separate Gemini
  integration, deliberately on a separate API key from the backend's extraction Gemini usage, so the
  two features never share a quota pool. Generates a fixed 3-insight narrative (positive/risk/
  opportunity, each with a recommended board action) from the computed metrics — not from the raw
  PDF.
- **Database**: PostgreSQL in production (Railway), SQLite for the test suite. No migration
  framework (no Alembic) — an idempotent `_add_missing_columns` step in `database.py` backfills new
  columns onto existing production tables on startup instead.

Full backend module-by-module breakdown: `backend/README.md`. Full frontend component breakdown:
`frontend/AGENTS.md`.

## Tech stack

| | |
|---|---|
| **Backend** | FastAPI (async) · SQLAlchemy 2.0 (async) · PostgreSQL / SQLite · PyMuPDF · Google Gemini (`google-genai`) · Pydantic v2 · pytest · Railway |
| **Frontend** | Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui + Radix · Recharts · next-themes · Vitest + Testing Library · Vercel |

## AI-assisted workflow

AI shows up in this project in two distinct ways — worth separating clearly:

### 1. AI as a feature of the app

- **Extraction**: deterministic parsing first, Gemini as a fallback/enrichment pass only when the
  deterministic baseline is incomplete — the app never depends on an LLM to get a real financial
  figure right when a reliable regex/table parse already exists.
- **AI Board Insights**: Gemini generates the dashboard's narrative commentary from already-computed
  metrics, gated by a content-hash cache so identical data never triggers a repeat API call (see
  `frontend/lib/insights-cache.ts`).

### 2. AI used to build the app

Development happened in two phases — see `docs/roadmap.md` for the full, detailed history.

**Phase 1 (2–6 July 2026, little AI assistance).** The project structure, backend foundation, PDF
extraction pipeline, `gemini_service.py`/`report_service.py`, and the initial dashboard shell were
organized and implemented directly. This established a working end-to-end pipeline — upload a PDF,
extract metrics, generate an AI-enriched report, render it on a dashboard — before any
AI-assisted-development workflow began.

**Phase 2 (6–8 July 2026).** Once that foundation existed, development was streamlined using
**Claude Code (Sonnet 5)** across 38 feature/fix branches, merged one at a time rather than as one
large change. The working pattern, used consistently:

1. **Plan before code** — for any nontrivial change, the agent explored the actual codebase first,
   proposed a concrete approach (naming exact files/functions to change), and got explicit sign-off
   from the developer before writing anything.
2. **Test and verify before merging** — every branch ran the full backend (`pytest`) and frontend
   (`vitest`) suites plus `tsc --noEmit`, and where practical was verified against the **real**
   deployed backend/production database directly (not just mocks) — e.g. regenerating the real
   report and confirming the API's exact output, or hitting the live download endpoint to confirm
   real (not assumed) behavior. UI changes were checked in an actual running browser, including
   Playwright-driven screenshots of hover/interaction states, not just component-test assertions.
3. **A recurring discipline, enforced repeatedly across branches**: never fabricate missing data.
   Missing values are `null`/`None`, never a guessed `0` or an interpolated default — this rule
   surfaced and was actively defended in the KPI sparkline history, the reporting-period
   extraction, the bookings figures, and the half-year/full-year cadence detection.
4. **Per-branch AI-usage docs**: `frontend/docs/ai-usage/*.md` records what was AI-generated vs.
   human-directed, notable decisions, and the verification performed, for most Phase 2 branches —
   the running log this section is itself distilled from.

## Assumptions

- **Two real filings are ingested: the HY2026 half-year results and the FY2025 Information
  Document.** Initially believed the half-year filing was the only real financial document Senus had
  ever published — a more thorough look at the investor relations page
  (`app.assiduous.tech/investor-relations/senus`), and finding the API it's built on (see "Investor
  relations API" below), turned up more real documents. The **Information Document (December
  2025)** — the Euronext listing prospectus, with FY2024/FY2025 annual figures — was extracted once
  its actual structure was inspected directly (a single summary table, much sparser than a full
  annual report; EBITDA and the Solvency/Returns ratios are genuinely undisclosed there and stay
  `null`, never guessed). **ADF Farm Solutions' audited Consolidated Financial Statements (30 June
  2025)** (Senus's predecessor entity, pre-re-registration) turned out to be a **scanned PDF with no
  text layer at all** — not extractable by this project's text-based pipeline without OCR or a
  vision-capable model call, a genuinely separate capability; see `docs/roadmap.md` for why this is
  left as a real, scoped future item rather than backfilled under time pressure or, worse,
  fabricated. Because the two ingested filings have different reporting cadences (6 months vs. 12
  months), an **extraction confidence service**
  (`backend/app/services/extraction_confidence.py`) scores every document before its data is trusted
  (0-100, tiered auto-accept/needs-review/reject) and a separate cadence check keeps them from ever
  being blended into one misleading trend line — both were built directly in response to a real
  production incident, documented in `docs/roadmap.md`. A **period selector** on the dashboard
  (`GET /metrics/dashboard/periods`, a `?document_id=` param on the summary/trend endpoints) lets a
  board reader deliberately pick which of the two real periods drives the whole page, instead of
  always showing whichever was extracted most recently.
- **This is a single-user tool**, not a multi-tenant product. The dashboard assumes one fixed
  presenter identity (a board member/CEO giving a live presentation) — there is no real
  authentication, login, or account system, by design, not as an oversight.
- **Uploaded PDF storage is not yet durable.** Railway's filesystem is ephemeral, so downloading the
  *original* uploaded PDF only works for documents uploaded since the most recent deploy — extracted
  metrics are unaffected, since they're persisted to Postgres immediately on upload and never
  re-read from disk afterwards.
- **Reporting cadence (half-year vs. full-year) is inferred from the filing's own language**
  ("six months ended" vs. "twelve months ended", etc.), not assumed. When a filing's cadence can't
  be determined from its text at all, the computed period-range fields are left `null` rather than
  defaulting to a guess.

## How outputs were validated

- **Automated tests**: 184 backend (pytest) + 152 frontend (Vitest) tests, run before every merge.
- **Type safety**: `tsc --noEmit` clean before every merge.
- **Manual validation against the real filing**: extracted figures (revenue, EBITDA, cash,
  customers, bookings) were cross-checked by hand against the source PDF during
  `feature/financial-metrics-expansion` and `feature/bookings-extraction`.
- **Manual validation of the Information Document extraction and confidence gate against a
  throwaway local database** (never production, for testing): uploaded the real filing and
  confirmed its figures matched the source PDF exactly; attempted importing a real governance
  filing (an AGM proxy notice) via the live investor relations API and confirmed it was rejected
  with a real, computed confidence score rather than silently creating a junk document; uploaded
  both real filings together and confirmed the revenue-trend chart correctly kept their different
  reporting cadences separate instead of blending them.
- **Manual validation against the live, deployed system** (not a local mock): confirmed via direct
  API calls against the real production database that a regenerated report produces the exact
  expected values end-to-end (e.g. `bookings: {value: "€700K", ...}`), and that the PDF-download
  endpoint's ephemeral-storage behavior was real, not theoretical, by hitting it against the actual
  deployed document and confirming the exact 404 response.
- **Live browser verification** for UI changes, including simulated interaction states (hover,
  theme toggles, form validation), not just component-level assertions.

## Local development

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, GEMINI_API_KEY
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
cp .env.example .env.local   # fill in NEXT_PUBLIC_API_URL, GEMINI_INSIGHTS_API_KEY
npm run dev
```

## Known limitations

- Uploaded-PDF download durability (see Assumptions above) — no object storage migration yet.
- No real authentication — intentional for a single-user tool, but would need addressing before any
  multi-user use.
- The Reports table's "PDF export" (of the AI-generated report itself, distinct from downloading the
  source upload) is not yet built.
- No bulk actions (bulk delete/download) on the Reports or Documents tables.
- The ADF Farm Solutions statements (Senus's other real historical filing) are a scanned PDF with no
  text layer — not extractable without OCR or a vision-capable model call, a genuinely separate
  capability from this project's text-based pipeline. See "Assumptions" above.
- The "Pending Review" extraction-confidence tag is shown on the Documents table but not yet the
  Reports table (same document underneath either way — a quick follow-up, not a gap in the
  underlying confidence gate itself, which applies everywhere already).
- The AI Board Insights panel's own (frontend-only, separate-API-key) Gemini integration is
  currently returning its static fallback content in production rather than real generated
  commentary — confirmed by directly calling the deployed `/api/insights` endpoint with genuinely
  different metrics and observing identical output. This needs `GEMINI_INSIGHTS_API_KEY`/quota
  checked on Vercel and Google AI Studio directly; it isn't a code bug in the sense of "wrong logic"
  (the panel's own prompt-building bug that could have caused this was found and fixed, see
  `docs/roadmap.md`) — but the route previously had no backoff at all, so every genuinely-new dataset
  kept blindly retrying an already-exhausted quota instead of giving it a chance to recover. Fixed by
  giving `/api/insights` the same circuit-breaker the backend's own Gemini integration already had
  (60s backoff on a rate-limit error, 24h on a billing/prepayment-exhausted one), plus persisting the
  insights cache to `localStorage` so a page reload no longer forces a fresh call for unchanged data.
  If the underlying cause turns out to be depleted prepayment credits rather than a recoverable rate
  limit, that part still needs manual billing action at ai.studio — no code change can conjure quota
  that isn't there — but the wasted-retry problem is fixed regardless.

## Further reading

- `docs/roadmap.md` — full build history, both the manual foundation phase and every
  Claude-Code-assisted branch.
- `docs/architecture.md` — system architecture and data-flow detail beyond the overview above.
- `backend/README.md` — backend module structure, route surface, deployment notes.
- `frontend/AGENTS.md` — frontend component structure and full design system (color, typography,
  layout decisions, and why they changed).
- `backend/docs/` — extraction-pipeline design notes, metrics-expansion plan.
- `frontend/docs/ai-usage/` — per-branch AI-usage/verification log.
