# System Architecture

> High-level overview lives in the root `README.md`. This document goes one level deeper into how
> data actually moves through the system. See `backend/README.md` for the backend's exact module
> layout, and `frontend/AGENTS.md` for the frontend's component structure and design system.

## Components

| Component | Runtime | Responsibility |
|---|---|---|
| `frontend/` | Next.js 16 (App Router), deployed on Vercel | Dashboard UI, polling-based data fetching, AI Board Insights generation |
| `backend/` | FastAPI (async), deployed on Railway | PDF ingestion, financial-metrics extraction, REST API |
| PostgreSQL | Railway | System of record — documents, extracted metrics, generated reports |
| Google Gemini | External API, two independent integrations | (1) backend extraction enrichment, (2) frontend AI Board Insights |

## Request/data lifecycle

### 1. Upload → extraction

```
User uploads PDF
  → POST /api/documents/upload  (backend/app/api/routes/documents.py)
    → PDFExtractionService.extract_text_from_upload  (PyMuPDF, saves to local disk)
    → SHA256 content-hash check (rejects exact-duplicate re-uploads)
    → FinancialMetricsExtractor.extract(text)   [deterministic, source of truth]
    → ReportService.generate_report(document_id)
        → if the deterministic baseline is incomplete: GeminiAnalysisService
          (fallback enrichment + narrative commentary only)
    → persisted: Document, FinancialMetrics, BalanceSheetMetrics, Report rows
```

The deterministic extractor runs first and is authoritative for every number it can find; Gemini is
only consulted when that baseline extraction is incomplete. This was a deliberate design choice —
narrative-leakage bugs (e.g. a forward-looking statement like "EBITDA positive by FY2028" being
misread as a real EBITDA figure) are why the extractor is context-aware (it isolates the P&L /
Balance Sheet / Cash Flow sections before parsing) rather than running regexes over the whole
document.

### 2. Dashboard read path

```
Dashboard mounts
  → useMetrics() / useChartData() / useReports()   (frontend/lib/hooks/)
    → GET /metrics/dashboard/summary
    → GET /metrics/dashboard/revenue-trend
    → GET /api/reports
  → each hook polls its endpoint every 60s independently
  → useAsyncData content-dedupes each poll result (unchanged data keeps the
    same object reference), so a no-op poll never triggers a re-render or
    a downstream AI Insights re-generation
```

### 3. AI Board Insights

```
AiInsights component receives `metrics` (already fetched, above)
  → checks a content-hash cache (frontend/lib/insights-cache.ts) — if this
    exact metrics object was already used to generate insights, skip
  → POST /api/insights   (frontend/app/api/insights/route.ts, Next.js Route
    Handler — keeps the Gemini key server-side, never shipped to the client)
    → Gemini generates 3 insights (positive/risk/opportunity), each with a
      recommended board action and a category tag matching the assignment's
      5 KPI categories
```

This is a **separate Gemini integration** from the backend's extraction usage — different API key,
different project, so the two features never compete for the same quota.

## Why no ORM migration framework

There's no Alembic (or equivalent) in this project. Schema changes to already-deployed tables are
applied via an idempotent `_add_missing_columns` step in `backend/app/core/database.py`, run on
every startup: it inspects each table's actual columns and adds anything missing via
`ALTER TABLE ... ADD COLUMN`. `Base.metadata.create_all` handles brand-new tables; this handles
columns added to tables that already exist in production. Chosen for a small, single-database
project over the overhead of a full migration framework.

## Known architectural limitations

- **Uploaded PDF storage is not durable.** Files are saved to Railway's local filesystem, which
  does not persist across deploys/restarts. Extracted metrics are unaffected (persisted to Postgres
  immediately), but downloading the *original* PDF only works for documents uploaded since the most
  recent deploy.
- **No real authentication.** `backend/app/core/security.py`'s `verify_api_key` is an intentional
  placeholder that always returns `True` — appropriate for this project's single-user scope, would
  need real implementation before any multi-user use.
- **Frontend is effectively a client-rendered SPA.** Nearly every component is a Next.js Client
  Component; the handful of Server Components that exist do no real server-side data fetching. This
  is an accepted tradeoff at this project's scale (a personal dashboard, not a bundle-size-sensitive
  public site), not an oversight — see the code-quality audit referenced in `docs/roadmap.md`.

## Historical note

An earlier planning document, `docs/DASHBOARD.md`, was written during Phase 1 (see
`docs/roadmap.md`) before most of the current architecture existed — it's kept for history but is
no longer accurate (e.g. it describes a top-nav search box and notification system that were later
removed as non-functional). This document is the current source of truth.
