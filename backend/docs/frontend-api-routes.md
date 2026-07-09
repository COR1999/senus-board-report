# Frontend API Routes

Use these backend endpoints from the Vercel frontend.

## Base URL

Set the frontend environment variable:

- NEXT_PUBLIC_API_URL=https://<your-railway-backend-url>

## Dashboard and metrics

- GET /metrics/dashboard/summary
  - Returns the full KPI set for the dashboard: revenue, customers, cash, EBITDA,
    ebitda_margin, cash_runway, interest_cover, roce, bookings, gross_margin,
    operating_margin, current_period, prior_period, data_extracted_at, document_id.
  - Optional `?document_id=` anchors the response on a specific reporting period
    instead of the true latest (see the period selector, PR #44).
- GET /metrics/dashboard/periods
  - Lists every reporting period eligible to appear on the dashboard (newest
    first), each with a combined bare-period + calendar-range label, for the
    period selector.
- GET /metrics/dashboard/revenue-trend
  - Always the full revenue/EBITDA/cash history (ignores `document_id` --
    the trend chart shows the whole history regardless of which period is
    selected elsewhere), each point tagged with its own `document_id` and
    `cadence_months`.
- GET /metrics/dashboard/cost-waterfall
  - Revenue -> Cost of Sales -> Gross Profit -> Operating Costs -> Operating
    Result -> D&A -> EBITDA. `available: false` (every figure `null`) is a
    normal response for a filing with no full cost breakdown, not a failure.
- GET /metrics/dashboard/historical-insight
  - Returns the persisted AI insight describing the trend across every report
    on file, or 404 if none is stored yet or the underlying chart data has
    changed since it was generated (fingerprint check).
- PUT /metrics/dashboard/historical-insight
  - Upserts the historical trend insight (called by the frontend's own
    `/api/insights` Gemini integration after a live generation).

## Reports

- GET /api/reports
  - Returns the list of reports.
- GET /api/reports/{report_id}
  - Returns a single report by ID.
- GET /api/reports/document/{document_id}
  - Returns reports for a specific document.
- POST /api/reports/document/{document_id}
  - Generates or retrieves a report for a document.
- POST /api/reports/{report_id}/regenerate
  - Regenerates a report.
- DELETE /api/reports/{report_id}
  - Deletes a report.
- GET /api/reports/{report_id}/dashboard
  - Returns the dashboard-shaped payload for one specific report.
- GET /api/reports/{report_id}/insights
  - Returns the persisted AI Board Insights for one report, or 404 if none
    generated yet.
- PUT /api/reports/{report_id}/insights
  - Upserts AI Board Insights for one report (create or replace; never appends).

## Documents

- POST /api/documents/upload
  - Upload a PDF file.
  - Form field name: file
  - Returns the created document with attached financial metrics.
- GET /api/documents
  - Lists documents.
- GET /api/documents/{document_id}
  - Gets one document by ID, including its extracted financial metrics and
    extraction-confidence tier/reasons.
- GET /api/documents/{document_id}/file
  - Downloads the original uploaded PDF (404 if not retained across a redeploy -- see "Known limitations" in the root README).
- POST /api/documents/{document_id}/approve
  - Promotes a `needs_review` document to dashboard-eligible after human
    review, without rewriting its underlying extraction_confidence score.
- DELETE /api/documents/{document_id}
  - Deletes a document.
- POST /api/documents/reconcile-periods
  - Idempotent sweep that merges any existing documents found to report the
    same period (see period_merge_service.py) -- mutates production data,
    only run with explicit confirmation.
- GET /api/documents/external/available
  - Lists filings on Senus's investor relations API not yet imported here (see the root README's "Investor relations API" section).
- GET /api/documents/external/hidden
  - Lists filings explicitly marked out of scope (see "hide" below).
- POST /api/documents/external/{attachment_id}/import
  - Downloads and ingests one filing from the investor relations API by its attachment_id.
- POST /api/documents/external/{attachment_id}/hide
  - Marks a filing as out of scope so it stops appearing in "available".
- POST /api/documents/external/{attachment_id}/unhide
  - Restores a hidden filing back to the "available" list.

## Example frontend usage

### Fetch dashboard metrics

```ts
fetch(`${process.env.NEXT_PUBLIC_API_URL}/metrics/dashboard/summary`)
```

### Upload a PDF

```ts
const formData = new FormData()
formData.append('file', file)

fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/documents/upload`, {
  method: 'POST',
  body: formData,
})
```

### Fetch reports

```ts
fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/reports`)
```
