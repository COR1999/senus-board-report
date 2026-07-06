# Backend Cleanup & Production-Readiness Pass (2026-07-06)

Full audit, bug-fix, and cleanup pass on `feature/pipeline_service` ahead
of the first Railway deployment and the move to frontend development.

## 1. Confirmed correctness bugs fixed

These were flagged as "still open" in `pipeline-service-improvements.md`
after a prior review; all four are now fixed and verified. Full detail
and verification notes are in that file's "Fixed (round 2)" section —
summary:

1. **`_to_number` couldn't parse values `_is_number` classified as
   valid** — `£`-prefixed values and parenthesized negatives
   (`"(120,000)"`) raised `ValueError` internally and silently became
   `0`. Fixed in `financial_metrics_extractor.py`.
2. **`_find_value_next_line` broke the same-line fallback** — it
   returned the raw next line (truthy) when no numeric token was found
   on it, which short-circuited `_extract_table_value`'s `or` and hid
   values that were actually present on the same line as the label.
   Fixed to return `None` so the fallback chain works correctly.
3. **Gemini 429 backoff never persisted** — `_disable_ai_temporarily` set
   `_ai_disabled_until` as a bare instance attribute instead of a class
   attribute, so the circuit breaker reset every time `ReportService`
   constructed a fresh `GeminiAnalysisService()` (i.e. every request).
   Fixed to write through the class attribute.
4. **Legitimate zero treated as "missing"** — `_baseline_is_complete` and
   the metrics merge in `report_service.py` used
   `not in (None, 0)`, so a real EBITDA of `0` (pre-revenue/break-even
   company) looked identical to "not found," burning unnecessary Gemini
   calls and letting hallucinated AI values override correct zeros.
   Fixed by having the extractor return `None` for genuinely-missing
   fields (distinct from a found `0`), and checking `is not None`
   throughout.

All four were verified with standalone scripts (no pytest dependency,
per the existing constraint at the time) exercising the extractor
functions directly, a class-attribute persistence check across fresh
`GeminiAnalysisService` instances, and a real (non-mocked) SQLite-backed
`ReportService.generate_report` run covering both a complete and an
incomplete baseline.

## 2. Additional bugs found and fixed during the cleanup pass

5. **`Settings()` crashed on startup** whenever `GEMINI_MAX_CALLS_PER_MINUTE`
   / `GEMINI_MAX_CALLS_PER_DAY` were set — which `.env.example` explicitly
   instructs users to do. Pydantic-settings rejects undeclared env vars
   by default, and those two were only ever read via `os.getenv(...)` in
   `gemini_service.py`, never declared on the `Settings` model. This
   would have broken every deployment that followed the documented setup.
   Fixed by declaring both fields on `Settings` and adding
   `extra="ignore"` as a safety net for any other platform-injected vars.
6. **Global exception handler returned a raw `dict`**, not a `Response`.
   FastAPI/Starlette exception handlers must return a `Response`
   instance — returning a plain dict here would have broken error
   handling for any unhandled exception in production instead of
   returning a clean 500. Fixed to return `JSONResponse(status_code=500, ...)`.
7. **`tests/conftest.py` imported from the dead `app.database` package**
   (`Base`, `async_engine`, `get_async_session` — none of which existed;
   see below), which broke pytest collection entirely — this is the
   "no working pytest install in this environment" caveat from the prior
   review. Fixed to import `Base`/`get_db` from `app.core.database`
   (the module actually used everywhere else), and added a
   Postgres-`JSONB`-as-SQLite-`JSON` compile shim so `Report.summary`
   creates correctly under the SQLite test database.
   **Result: the test suite went from 0 collectible tests to 10/10 passing.**

## 3. Dead code and dead files removed

Verified unused (zero imports/references anywhere in the codebase)
before removal — nothing here was guessed at:

- **`app/database/` (entire package)** — this was the "I suspect the
  database folder may be unused" item. Confirmed: `session.py` and
  `__init__.py` were fully commented out, and `base.py` defined a `Base`
  that no model used. Every model (`Document`, `FinancialMetrics`,
  `Report`) imports `Base` from `app/core/database.py` instead, which is
  the real, active database module. `app/database/` was 100% dead.
- **`app/services/financial_metrics_extractor.py.outdated`** — a stray
  pre-rewrite backup file left in the source tree.
- **`app/schemas/report.py`** — entirely unused; nothing imported from
  it anywhere. It also duplicated (with different definitions) class
  names already present in `app/schemas/financial.py`, which is a
  correctness trap waiting to happen.
- **Unused `Report*`/`HealthResponse` classes inside `app/schemas/financial.py`**
  — `ReportBase`, `ReportCreate`, `ReportResponse`, `ReportWithDocument`,
  `HealthResponse` were only ever re-exported by `schemas/__init__.py`,
  never consumed by any route (the reports API returns ORM objects
  directly; `/health` returns a plain dict). `HealthResponse`'s fields
  didn't even match what `/health` actually returns, confirming it was
  stale. Removed, along with the now-unused `List`/`Dict`/`Any` imports
  that only existed for them.
- **`app/utils/test_gemini_integration.py`** — every test in this file
  called methods/constructor kwargs that no longer exist on
  `GeminiAnalysisService` (`extract_financial_metrics_from_text`,
  `_generate_fallback_commentary`, `_chunk_text`, `_get_multiplier`,
  `enable_cache=`). 100% would fail if run. Deleted.
- **One stale test in `tests/test_integration.py`**
  (`test_metric_extraction_fallback`) called the same removed
  `extract_financial_metrics_from_text` method. Removed just that test;
  the other 10 tests in the file were valid and now pass.
- **`backend/venv/`** — a second, broken virtualenv sitting alongside the
  real one (`.venv/`): only 7 packages installed, no `python.exe`. Dead
  weight, git-ignored either way. Removed; `.venv/` is the one in use.

## 4. `requirements.txt`: encoding fix + unused-package trim

- **The file was UTF-16-encoded** (likely from a PowerShell redirect
  without `-Encoding utf8`). This is a hard blocker for Railway/pip —
  `pip install -r requirements.txt` cannot parse it. Rewritten as plain
  UTF-8.
- **It was a full `pip freeze` dump of the dev virtualenv**, not a
  direct-dependency list — 70 packages, many of them orphaned. Verified
  via `pip show <pkg>` (`Required-by` chains) and confirmed against
  actual `import` statements in the codebase, then proved by installing
  the trimmed file into a brand-new empty virtualenv and successfully
  importing `app.main`. **23 packages removed**, all confirmed to have
  zero reverse dependencies among the packages actually kept:
  - `numpy`, `pandas` — unused; nothing depends on `pandas`, and `numpy`
    was only there for `pandas`.
  - `openai`, `tqdm`, `jiter`, `distro`* — `openai` SDK is never
    imported anywhere despite `OPENAI_API_KEY` existing in `Settings`
    (see "deferred items" below); `tqdm`/`jiter` were only required by
    `openai`. (*`distro` is also required by `google-genai`, so it was
    kept.)
  - `pi` — a stray, unrelated package with zero reverse dependencies and
    zero imports anywhere. Origin unclear; almost certainly an accidental
    `pip install`.
  - `python-dateutil`, `six`, `tzdata` — only required by `pandas`.
  - The entire legacy Google API client stack — `google-ai-generativelanguage`,
    `google-api-core`, `google-api-python-client`, `google-auth-httplib2`,
    `googleapis-common-protos`, `grpcio`, `grpcio-status`, `proto-plus`,
    `protobuf`, `uritemplate`, `httplib2`, `pyparsing`. The code only uses
    the modern unified `google-genai` SDK (`from google import genai`),
    whose actual declared dependencies are just `anyio`, `distro`,
    `google-auth`, `httpx`, `pydantic`, `requests`, `sniffio`, `tenacity`,
    `typing-extensions`, `websockets`. This legacy stack (including the
    heavyweight `grpcio`/`protobuf` binary wheels) was never required by
    anything actually used.
  - `Mako`, `MarkupSafe` — zero reverse dependencies at all; not required
    by SQLAlchemy or anything else installed.
  - This meaningfully cuts install time and slug size on Railway.

## 5. Other production-readiness fixes

- **`.python-version` added** (`3.11`) so Railway's Nixpacks builder
  matches the Python version this app is developed and tested against
  (previously unpinned).
- **`docs/frontend-api-routes.md` updated** — it still documented the
  manual metrics CRUD endpoints (`GET/POST /metrics`, `GET
  /metrics/{document_id}`) that were removed from `metrics.py` in an
  earlier pass. Removed from the doc to match the real route surface.
- **`app/api/routes/__init__.py` fixed** — it re-exported
  `documents_router`/`metrics_router` but silently omitted
  `reports_router`. Added for correctness (nothing currently imports
  this re-export bundle, but it was wrong either way).
- **Backend `README.md` added** — project structure, route table, env
  var reference, local dev/test instructions, and Railway deployment
  notes (see `backend/README.md`).

## 6. Reports API: response_model wiring + summary shape fix

While removing the dead `app/schemas/report.py` (see above), a follow-up
question came up: `reports.py` never used `response_model=` on any
endpoint in the first place (before *or* after this cleanup) — it always
returned raw SQLAlchemy `Report` ORM objects directly. That meant:

- Swagger/OpenAPI docs for `/api/reports/*` showed untyped responses,
  which would have produced untyped/`any` TypeScript on the frontend.
- Nothing enforced a consistent shape for `report.summary["metrics"]` —
  it could mix plain floats (baseline-sourced) and `{"value": N}` dicts
  (AI-sourced) across different keys in the same response (tracked as
  item 7 in `pipeline-service-improvements.md`).

Fixed properly instead of just leaving it noted:

- Recreated `app/schemas/report.py` with real, used schemas:
  `ReportResponse`, `ReportSummary`, `ReportMetricsSummary`,
  `ReportDeleteResponse`, `ReportDashboardResponse`, `DashboardDocument`.
- Wired `response_model=` onto every endpoint in `reports.py`.
- Added `ReportService._plain_metric_value` and applied it to
  `merged_metrics` in `_generate` right after the baseline/AI merge, so
  `report.summary["metrics"]` is always a flat `{key: float | None}`
  shape — unwrapping AI's `{"value": N}` without collapsing a genuinely
  missing value into `0` (that would have undone fix #4 above).
- Verified end-to-end (not just unit-level) with a real `TestClient`
  request cycle against a real SQLite-backed app: upload → generate
  report → get → list → dashboard → regenerate → delete, confirming the
  new schemas validate real data and `summary.metrics` now returns plain
  numbers everywhere.

## 7. Verified, not changed

- Confirmed (before the response_model wiring above existed) that a raw
  SQLAlchemy ORM object returned with no `response_model` serializes
  cleanly via FastAPI's `jsonable_encoder` — initially suspected as a
  risk given `_sa_instance_state` lives in `__dict__`, but empirically
  confirmed fine.
- Confirmed the trimmed `requirements.txt` installs cleanly into a fresh
  virtualenv and that `app.main` imports successfully from it.
- Confirmed `.env` (real Railway Postgres URL, Gemini key, OpenAI key)
  has never been committed to git history on any branch — it is
  correctly git-ignored. No secret-leak remediation needed, but see
  below.

## 8. Deferred / flagged for awareness (not changed)

- **Rotate the credentials in the local `backend/.env` file** as a
  hygiene measure — a real Railway Postgres connection string and live
  Gemini/OpenAI API keys are sitting in plaintext on disk. They're not
  in git history, but it's worth rotating them before/after this
  cleanup out of caution, since this wasn't something to fix in code.
- **`OPENAI_API_KEY` setting is dead config** — declared on `Settings`
  and documented in `.env.example`, but the `openai` package isn't
  installed anymore (it wasn't used) and nothing reads this key. Left
  in place in case it's intentional groundwork for a future fallback
  provider; remove it if not.
- **`app/core/security.py`** is an intentional placeholder
  (`verify_api_key`, always returns `True`) for future auth. Not wired
  into any route today. Left as-is.
- **Uploaded PDFs live on ephemeral local disk** (`uploads/`) — lost on
  every Railway restart/redeploy. Not a functional problem today since
  extracted text is persisted to Postgres immediately and nothing
  re-reads the file afterwards, but there's no "view/download the
  original PDF" capability. Move to object storage if that's ever needed
  — documented in `backend/README.md`.
- **`docs/change-overview.md` and `docs/financial-metrics-fallback-fix.md`**
  are historical write-ups from an earlier, already-merged PR. Left
  untouched as historical record — they don't claim anything about the
  current route surface.

## Suggested commit message

```
Backend cleanup and production-readiness pass for Railway deploy

Fix 4 confirmed extractor/service bugs (£/parenthesized-negative
parsing, same-line fallback short-circuit, Gemini 429 backoff not
persisting across requests, legitimate-zero-vs-missing metric
handling), plus a Settings() startup crash on documented env vars and
a broken global exception handler. Remove the dead app/database
package, dead schemas, two broken test files, and a stale .outdated
extractor backup. Rewrite requirements.txt as UTF-8 (was UTF-16, a
hard install blocker) and drop 23 unused/orphaned packages, verified
via a clean-venv install. Restore a working pytest suite (was fully
broken via a dead import; now 10/10 passing) and pin the Python
version for Railway's builder. Add backend README and cleanup docs.
```
