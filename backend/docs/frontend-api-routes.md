# Frontend API Routes

Use these backend endpoints from the Vercel frontend.

## Base URL

Set the frontend environment variable:

- NEXT_PUBLIC_API_URL=https://<your-railway-backend-url>

## Dashboard and metrics

- GET /metrics/dashboard/summary
  - Returns KPI cards for revenue, customers, cash, and EBITDA.

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

## Documents

- POST /api/documents/upload
  - Upload a PDF file.
  - Form field name: file
  - Returns the created document with attached financial metrics.
- GET /api/documents
  - Lists documents.
- GET /api/documents/{document_id}
  - Gets one document by ID.
- DELETE /api/documents/{document_id}
  - Deletes a document.

## Metrics

- GET /metrics
  - Lists metrics rows.
- GET /metrics/{document_id}
  - Gets metrics for a specific document.
- POST /metrics
  - Creates or updates metrics for a document.

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
