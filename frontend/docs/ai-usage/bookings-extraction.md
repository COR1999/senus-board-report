# AI Usage — feature/bookings-extraction

## What was built

Adds the "Bookings" KPI named in the assignment brief's Growth & Revenue
section, which had no backing data anywhere in the system before this
branch:

- Investigated whether the real filing supports a segment-level
  (Government/Corporate/Agriculture) revenue breakdown, per an earlier
  roadmap item. Direct inspection of the real extracted PDF text found no
  such structured data exists anywhere in the filing — only generic
  narrative descriptions of customer types. That item was closed as
  infeasible and this Bookings extraction was built instead.
- `FinancialMetricsExtractor` gained a narrative-regex extraction for
  closed bookings value, the customer count behind it, and open pipeline
  value, from the filing's one sentence describing new business ("pipeline
  deals of approx. €700k across 21 enterprise customers closed in the
  period (further approx. €500k of open pipeline)").
- Three new `FinancialMetrics` columns (`bookings_value`,
  `bookings_customers`, `bookings_pipeline`) plus the matching production
  migration entries (no Alembic in this project — see
  `_add_missing_columns` in `backend/app/core/database.py`).
- A new `bookings` KPI on `GET /metrics/dashboard/summary` and a 5th
  Growth & Revenue dashboard card, with a subtitle ("new business closed
  this period") spelling out what Bookings means versus Revenue, per the
  user's request.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). The
decision to abandon segment-extraction and build Bookings instead was
presented to the user as a recommendation after the real-filing
investigation, and approved by the user before implementation began.

## Notable decisions made along the way

- **Narrative-regex, not structured-table extraction**: unlike
  revenue/cash/EBITDA (which come from actual P&L/balance-sheet/cash-flow
  tables), Bookings only exists as prose in this filing. It's extracted
  with the same reliability class as the pre-existing `customers` field —
  a real but more fragile keyword-anchored regex, documented as such in
  the code rather than presented as equivalent to the structured-table
  fields.
- **No prior-period comparative for Bookings**: the filing states this
  quarter's closed bookings but no prior-period bookings figure to diff
  against (unlike revenue/cash/EBITDA, which do have prior columns from
  `feature/financial-metrics-expansion`). `change`/`trend` are hardcoded to
  `0`/`neutral` rather than fabricated — the same pattern already used for
  `customers`.
- **Dedicated `bookings_kpi()` helper, not the shared `build()` helper**:
  caught before committing that reusing `build()` would render a missing
  bookings value as `"€0"` via `format_currency(None)`'s zero-default,
  misrepresenting "not extracted" as a real zero. Wrote a small dedicated
  function that returns `"N/A"` when `bookings_value is None` instead.
- **Missing-vs-zero convention held**: `bookings_value`/`bookings_customers`/
  `bookings_pipeline` all stay `None` (never `0`) when the sentence isn't
  found, consistent with the rest of this codebase's established handling.
- **Dashboard grid**: Growth & Revenue row grew from 4 to 5 cards
  (`lg:grid-cols-4` → `lg:grid-cols-5`); the separate Cash/Solvency/Returns
  row was left untouched at 4.

## Verification performed

- `cd backend && pytest tests/` — 74 passed, including new tests for: the
  closed-bookings-value/customer-count extraction, the open-pipeline
  extraction, a missing-sentence case staying `None` (not `0`), and the
  dashboard summary's `bookings` KPI showing `"N/A"` vs. a formatted value.
- `TestExtractAgainstRealFiling` extended with the 3 new bookings
  assertions run against the actual uploaded PDF, not just synthetic text
  — extracted `bookings_value=700000.0`, `bookings_customers=21`,
  `bookings_pipeline=500000.0` correctly.
- `cd frontend && npx vitest run` — 69 passed; `npx tsc --noEmit` — no
  errors.
- Manually verified the database migration against the real, already
  existing production `financial_metrics` table (startup logs confirmed
  "Adding missing column financial_metrics.bookings_value" etc., not just
  a fresh local database), then regenerated the real report end-to-end and
  confirmed `GET /metrics/dashboard/summary` returns
  `"bookings": {"value": "€700K", "change": 0.0, "trend": "neutral", "history": [700000.0]}`
  alongside correct values for every other existing KPI.
- Real OpenAI call not verified end-to-end this session (AI Insights panel
  uses a separate, pre-existing integration untouched by this branch).
- Visual check of the new Bookings card's styling in a browser not
  available this session — happy to walk through it live if you open a
  localhost for me to test against, as with prior branches.
