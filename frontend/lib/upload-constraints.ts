// Shared with the backend's own limit (backend/app/api/routes/documents.py) --
// checked here too so a user gets instant feedback without waiting on a
// network round-trip for an oversized file. 20MB matches the only existing
// precedent in this repo (DELIVERY_READINESS_REPORT.md's original upload
// spec), which was never actually enforced anywhere until now.
export const MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
export const MAX_UPLOAD_SIZE_LABEL = '20MB'
