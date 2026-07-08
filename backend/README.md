# Senus Board Intelligence Platform — Backend

FastAPI backend that ingests financial-report PDFs, extracts structured
financial metrics (deterministic parser + optional Gemini AI enrichment),
and serves a reporting/dashboard API for the frontend.

## Stack

- **FastAPI** (async) + **Uvicorn**
- **SQLAlchemy 2.0** (async) — **PostgreSQL** in production, SQLite for tests
- **PyMuPDF (`fitz`)** for PDF text extraction
- **Google Gemini** (`google-genai`) for optional AI enrichment, with a
  deterministic regex/table-based extractor as the source of truth
- **Pydantic v2** for settings and schemas

## Project structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app factory, CORS, lifespan, exception handler
│   ├── core/
│   │   ├── config.py             # Settings (env vars), see "Environment variables" below
│   │   ├── database.py           # Async SQLAlchemy engine/session + declarative Base
│   │   └── security.py           # Placeholder for future auth (not wired up yet)
│   ├── api/routes/
│   │   ├── documents.py          # Upload / list / get / delete documents
│   │   ├── reports.py            # Generate / regenerate / get / delete reports, dashboard payload
│   │   └── metrics.py            # GET /metrics/dashboard/summary (read-only, internal-write-only)
│   ├── models/                   # SQLAlchemy ORM models: Document, FinancialMetrics, Report
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/
│   │   ├── pdf_service.py                  # Save + extract text from uploaded PDFs
│   │   ├── financial_metrics_extractor.py  # Deterministic P&L/balance-sheet/cash-flow parser
│   │   ├── gemini_service.py               # Gemini client: caching, quota/rate limiting, JSON parsing
│   │   ├── report_service.py               # Orchestrates extraction + AI enrichment + persistence
│   │   └── metrics_service.py              # Formatting/derived-metric helpers (currency, CAGR, etc.)
│   └── utils/                    # Empty — reserved for future shared helpers
├── tests/                        # pytest suite (see "Testing" below)
├── docs/                         # Design notes and change history for past PRs
├── reset_db.py                   # Dev utility: drop/recreate tables via init_db()
├── test_api_manual.py            # Manual smoke-test script against a running server (not pytest)
├── requirements.txt
├── Procfile                      # Railway/Heroku-style start command
└── .python-version               # Pins the Python version for Railway's Nixpacks builder
```

### Route surface

| Router | Routes |
|---|---|
| documents | `GET /api/documents`, `POST /api/documents/upload`, `GET/DELETE /api/documents/{id}` |
| reports | `GET /api/reports`, `GET/POST /api/reports/document/{id}`, `GET/DELETE /api/reports/{id}`, `GET /api/reports/{id}/dashboard`, `POST /api/reports/{id}/regenerate` |
| metrics | `GET /metrics/dashboard/summary` |
| system | `GET /`, `GET /health` |

Financial metrics have no client-facing create/update endpoint by design —
they're always written internally by `ReportService` during report
generation (see `metrics.py`).

## Environment variables

Copy `.env.example` to `.env` for local development. **`.env` is
git-ignored and must never be committed** — set the real values as
environment variables in the Railway project dashboard for production.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://...` — converted to `postgresql+asyncpg://` automatically |
| `GEMINI_API_KEY` | No | AI enrichment is skipped (safe fallback) if unset |
| `GEMINI_MAX_CALLS_PER_MINUTE` | No | Default `10` — proactive rate-limit cap |
| `GEMINI_MAX_CALLS_PER_DAY` | No | Default `1000` — proactive rolling 24h cap |
| `ENVIRONMENT` | Yes (prod) | Set to `production` on Railway |
| `DEBUG` | Yes (prod) | Set to `False` on Railway — enables permissive CORS (`*`) and leaks exception detail when `True` |
| `FRONTEND_URL` | Yes | Deployed frontend origin, added to the CORS allow-list |

## Local development

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # then fill in real values
uvicorn app.main:app --reload
```

## Testing

```bash
pytest tests/ -v
```

The suite runs against an in-memory SQLite database (`tests/conftest.py`),
with a compatibility shim so the Postgres-only `JSONB` column type used by
`Report.summary`/`key_findings` compiles under SQLite as plain `JSON`.

`test_api_manual.py` (repo root) is a separate manual smoke-test script for
a *running* server — it is not part of the pytest suite.

## Production deployment (Railway)

- **Start command** (`Procfile`): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Python version** is pinned via `.python-version` (`3.11`) so Railway's
  Nixpacks builder matches the version this app is tested against.
- Set `DATABASE_URL`, `GEMINI_API_KEY`, `ENVIRONMENT=production`,
  `DEBUG=False`, and `FRONTEND_URL` as Railway environment variables (not
  via a committed `.env`).
- **Uploaded PDFs are stored on local disk** (`uploads/`), which is
  ephemeral on Railway — files will not survive a redeploy or restart.
  This is not a functional problem for the extracted metrics (persisted to
  Postgres immediately on upload, never re-read from disk afterwards), but
  it does affect `GET /api/documents/{id}/file` (download the original
  PDF): that endpoint only works for documents uploaded since the most
  recent deploy/restart. Confirmed empirically (2026-07-08) against the
  real deployed document — its DB row and metrics were intact, but the
  file itself was already gone, and the endpoint returned a 404 with a
  clear "no longer available" message rather than a generic error. Move to
  object storage (e.g. S3/R2) if reliable long-term download matters.
- CORS automatically allows all origins (`*`) when `DEBUG=True` or
  `ENVIRONMENT=development` — make sure both are set correctly in
  production so this widening doesn't apply.

## Further reading

See `docs/` for design notes and historical change write-ups, including
`docs/pipeline-service-improvements.md` (extractor rewrite, Gemini quota
protection, and the confirmed-bug fixes from the latest cleanup pass) and
`docs/backend-cleanup-2026-07.md` (full audit/cleanup summary).
