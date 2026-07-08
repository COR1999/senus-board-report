# AI Usage — fix/financial-metrics-nullable-columns

## Context

Found immediately after PR #50 merged and deployed: the user tested the real fix by importing ADF
Farm Solutions into production. Extraction itself worked perfectly — revenue €836,991, cash
€140,135, EBITDA -€613,313, 85% confidence — but the import still failed with a `500`, this time from
Postgres, not Gemini.

## The bug

```
NotNullViolationError: null value in column "customers" of relation "financial_metrics"
violates not-null constraint
```

`FinancialMetrics.customers` has been declared `Mapped[Optional[int]]` in the SQLAlchemy model for a
long time — but `Base.metadata.create_all` (this project's only schema-creation mechanism; there's no
Alembic) only creates *missing* tables. It never alters an *existing* table's column constraints. The
live production `financial_metrics` table has existed since very early in the project, likely from
before the "missing value is `None`, never a fabricated/required value" convention was fully
established — so its `customers` column still has a `NOT NULL` constraint left over from whenever it
was first created, even though the model has said otherwise for a long time.

This had never been hit before because every document successfully ingested so far happened to report
a real customer count (HY2026: 138, the Information Document: 36 via narrative extraction). ADF Farm
Solutions was the first real document to genuinely not disclose one — and the first to actually
attempt a `NULL` insert for that column in production.

Applied the same fix proactively to `revenue`, `cash`, `ebitda`, `gross_margin`, and
`operating_margin` — the other five columns from `financial_metrics`' original release, none of which
have ever been proven NULL-safe in production either (every document so far happened to report a
value for all of them too). Fixing only `customers` reactively would leave the same class of bug
waiting to resurface the next time one of those genuinely comes back empty.

## The fix

Extended the existing idempotent migration pattern in `database.py` (the same one that backfills
missing *columns* on startup) with a parallel, Postgres-only step that runs
`ALTER TABLE financial_metrics ALTER COLUMN {column} DROP NOT NULL` for each of the six columns.
Skipped entirely on SQLite (every test/local run), since SQLite's `ALTER TABLE` doesn't support
altering column constraints at all, and none of those tables ever had the stale constraint to begin
with. Idempotent by nature — dropping a constraint that's already absent is a harmless no-op in
Postgres, so no existence check is needed before running it, unlike the column-add loop.

## Verification performed

- `pytest tests/` — 207 passed (2 new: confirms the migration is a clean no-op on SQLite, and — since
  real Postgres isn't available in this test environment — a test using a minimal fake connection
  object to verify the exact `ALTER TABLE ... DROP NOT NULL` statement is constructed for all six
  columns, without needing a live database to prove the SQL-generation logic itself is correct).
- Not yet re-verified against the live ADF Farm Solutions import — that's the real end-to-end test,
  pending this PR's merge and deploy. The earlier failed attempt already fully committed a `Document`
  row and a `Report` stuck at `status="generating"` in production (the claim-locking commit inside
  `generate_report` happens *before* the failing `FinancialMetrics` insert) — re-importing the same
  file will 409 on the content-hash duplicate check rather than retry. Needs a `POST
  /api/reports/{id}/regenerate` call against that specific document once this deploys, not a fresh
  import.
