# Backend Change Overview

## Summary

This change set fixes the backend financial-metrics flow for uploaded PDFs and makes the dashboard summary reflect the latest metrics more reliably.

## What changed

- Fixed the fallback report-generation path so extracted values are normalized and persisted into the financial metrics model.
- Ensured document upload/list responses include the latest financial metrics for the uploaded document.
- Hardened the metrics endpoint so posting metrics for a missing document returns a clear 404 instead of failing with a server error.
- Added regression coverage around the upload + metrics flow and the missing-document case.
- Documented the fallback-metrics issue and fix in the backend docs folder.

## Files involved

- [backend/app/services/report_service.py](backend/app/services/report_service.py)
- [backend/app/api/routes/documents.py](backend/app/api/routes/documents.py)
- [backend/app/api/routes/metrics.py](backend/app/api/routes/metrics.py)
- [backend/app/models/financial_metrics.py](backend/app/models/financial_metrics.py)
- [backend/app/schemas/financial.py](backend/app/schemas/financial.py)
- [backend/tests/test_upload_metrics.py](backend/tests/test_upload_metrics.py)
- [backend/docs/financial-metrics-fallback-fix.md](backend/docs/financial-metrics-fallback-fix.md)

## Verification

The backend metrics endpoint was verified live for:
- successful metrics creation for an existing document,
- a 404 response for a missing document ID,
- and dashboard summary responses reflecting the latest values.
