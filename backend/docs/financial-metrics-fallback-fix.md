# Financial Metrics Fallback Fix

## Issue

When a PDF was uploaded and Gemini was unavailable or hit its quota, the backend could still parse the document text successfully, but the financial metrics returned to the client were missing or empty.

This meant that the upload flow worked from a document-processing perspective, but the downstream FinancialMetrics response did not contain the expected values.

## Root Cause

The problem was in the fallback path used when Gemini could not provide structured metrics.

The backend was:
- successfully extracting document text from the PDF,
- generating fallback commentary/findings,
- but not consistently converting those fallback values into the FinancialMetrics model used by the API.

In other words, the PDF parsing worked, but the bridge between the fallback output and the persisted financial metrics data was incomplete.

## Fix Applied

The backend now:
1. Normalizes fallback-generated values into a consistent metrics payload.
2. Persists those values into the FinancialMetrics table for the uploaded document.
3. Returns the latest metrics as part of the document upload response and document listing responses.

This ensures that even when Gemini is unavailable, the API still returns usable financial metrics data for the uploaded document.

## Result

The document upload flow now supports a reliable fallback path:
- PDF text extraction still works,
- report generation still completes,
- and financial metrics are available in the backend response even when Gemini is not available.

## Notes for Documentation

This fix was implemented in the backend to ensure the financial metrics pipeline remains resilient when AI services are rate-limited or unavailable.
