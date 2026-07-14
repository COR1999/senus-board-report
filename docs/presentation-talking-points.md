# Presentation talking points

Prep material for discussing this project with interviewers — organized by theme, each with a
short real story and a discussion question. Drawn from the actual commit history and this session's
own debugging, not generic claims. PR numbers refer to commits on `main`; branch names refer to
`frontend/docs/ai-usage/<branch>.md` if you want the full writeup on any of them.

## 1. Missing vs. fabricated data

**The rule**: a genuinely undisclosed figure is `null`, never `0` — enforced everywhere in this
codebase, not just as a style preference.

**The incident (#40)**: importing a non-financial document (an AGM notice) through the investor-
relations sync exposed a real bug — a missing revenue/customers/cash/ebitda defaulted to `0`
instead of `None`, and the dashboard's "pick the latest period" logic had no way to recognize an
all-zero row as *empty* rather than *real*. An unrelated document silently blanked out the live
half-year filing's numbers on the production dashboard. Six bad documents had to be deleted from
production directly before the fix even landed.

*Ask me: why is `None` vs `0` treated as a correctness bug, not a style nitpick?*

## 2. AI reliability at the edges

**Deterministic-first, AI as enrichment, never source of truth**: the extractor tries regex/table-
based parsing first; Gemini is only called when that baseline is incomplete, and even then the
baseline's own values always win a merge conflict. Confirmed today, live: a filing whose baseline
extraction was already complete (`_baseline_is_complete`) never calls Gemini at all.

**Vision extraction is measurably less reliable than text extraction — and the product design
accounts for that, not just the messaging.** Confirmed directly across this session: identical
scanned-file vision calls sometimes recognize the reporting period, sometimes don't. That's why it's
gated behind the confidence-tier system (`needs_review`/`rejected`) rather than trusted at face
value.

**A real cost/reliability bug fixed today**: the circuit breaker that backs off Gemini calls after a
429 was classifying an ordinary daily-quota message as a full billing outage — because Google's
routine quota-exceeded message happens to contain the word "billing" in its own boilerplate, and the
original check just did a substring match on that word. Self-inflicted a 24-hour AI-insights outage
from what should've cleared in 60 seconds. Caught by actually driving the live app end-to-end, not by
reading the code.

*Ask me: what's the actual cost/reliability tradeoff of calling an LLM on every document, vs. only
when the deterministic path fails?*

## 3. Reconciling multiple sources of truth

**Same period, two documents, different figures — never silently resolved.** `period_merge_service`
detects when two independently-uploaded filings report the exact same reporting period (matched on
`reporting_period_start`/`end`, not a fuzzy guess) and merges them into one record. Where they agree,
it's a clean `auto_accept` merge. Where they *disagree* on the same field, the merged row is tagged
`needs_review` with both candidate values and their source filenames recorded — never picked
automatically in favor of whichever ran more recently.

**The bug that motivated it (#53, #54)**: ADF Farm Solutions and the Information Document both
genuinely report FY2025. Before the merge service existed, they showed as two unexplained duplicate
periods; worse, ADF's revenue was being diffed against the Information Document's *own current*
figure instead of a real prior year, because nothing could tell two full-year filings apart from a
half-year one (vision extraction had no cadence signal at all).

**Found again, live, this session**: exactly this — vision extraction not returning a parseable
reporting period, blocking the merge from triggering. Fixed by making the vision prompt request an
exact, regex-matchable phrasing instead of a freeform description, then verified directly against
the real API.

*Ask me: what happens when two source documents disagree on the same number?*

## 4. Confidence gating & human-in-the-loop

Every extraction gets a 0–100 score and a tier: `auto_accept` (≥95%), `needs_review` (85–94%),
`rejected` (<85%) — a document that doesn't match a known financial-statement format at all scores 0
outright, regardless of any narrative-regex hits elsewhere, so it's always `rejected` too. A `needs_review`
row is excluded from every dashboard endpoint until a human explicitly approves it via the Documents
page's review panel — the score/tier itself is never rewritten on approval (it's a permanent, honest
record of what the extractor actually found); approval is tracked as a separate `human_approved_at`
timestamp.

**Real gap found and fixed (#52)**: the confidence gate existed before the review UI did — a
`needs_review` document was flagged correctly but there was no way for a human to actually see the
extracted figures or promote it. *"I have no way to review the document"* was the literal user
complaint that drove this.

*Ask me: why is the confidence score never overwritten, even after a human approves the document?*

## 5. Schema evolution against a live database, no migration framework

There's no Alembic in this project — schema changes are applied by an idempotent
`_add_missing_columns` step that runs on every startup, checking via the inspector whether each
column/constraint already exists before touching it.

**Real incident (#51)**: importing ADF Farm Solutions in *production* hit a `NotNullViolationError`
on `customers` — the SQLAlchemy model had said `Optional[int]` for a long time, but
`Base.metadata.create_all` never alters an *existing* table's column constraints, so the live
Postgres column still carried a leftover `NOT NULL` from whenever the table was first created. Every
document ingested up to that point happened to report a value, so the gap was invisible until it
wasn't. Fixed proactively for all six original-release columns, not just the one that broke.

*Ask me: how do you evolve a live production schema without a migration tool?*

## 6. Engineering process & discipline

- **N+1 query + over-fetching**, found in a self-initiated code audit, not a bug report: the document
  list endpoint issued one `FinancialMetrics` query per row and returned full extracted PDF text (tens
  of KB per document) for a table that only renders filename/status/size/date.
- **CI catching what local testing couldn't**: two failures that only ever showed up in GitHub
  Actions (Linux) — a test reading a gitignored runtime file that happened to exist locally, and an
  `anyio` fixture scope mismatch that Windows' plugin-registration order silently tolerated. Neither
  reproduced locally despite identical package versions.
- **Adaptive UI, never a fake empty state**: the KPI strip, cost waterfall, and growth-forecast cards
  all render *nothing* rather than a placeholder when a filing doesn't disclose the underlying data —
  same discipline that's now enforced for Presentation Mode's own pre-seeded baseline (see below).

*Ask me: what's a bug you found through auditing your own code, not from a bug report?*

## 7. Meta: this demo tool itself

Presentation Mode (the guided walkthrough you're clicking through) and its local, fully-isolated
demo environment were both built in this same session — deliberately separate from touching
production. Building it surfaced three more real, previously-unknown bugs along the way (the quota
misclassification above, a reports-list bug showing superseded documents as unexplained duplicates,
and the vision reporting_period gap) — none hypothetical, all confirmed by actually running the app
end-to-end rather than reading the code and assuming it worked.

*Ask me: what did you find by actually using your own product live, that you wouldn't have found by
reading the code?*
