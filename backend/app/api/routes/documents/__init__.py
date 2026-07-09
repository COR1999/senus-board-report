"""
Document upload and management endpoints.
Integrates PDF extraction with Report generation and FinancialMetrics system.

Split by concern (each was previously a section of one ~630-line file):
- `_core.py` -- upload, get, list, delete, download, approve, reconcile.
- `_external_sync.py` -- the investor-relations "available/hidden/hide/
  unhide/import" endpoints.

`pdf_service`, `MAX_UPLOAD_SIZE_BYTES`, `_effective_tier`,
`build_document_response`, and `_ingest_document` stay defined directly in
this file rather than moving to a submodule, and every route handler is
re-exported below -- both deliberate: several tests
(`test_document_dedup.py`, `test_upload_metrics.py`, etc.) call these route
functions directly (bypassing FastAPI's request/DI layer) and monkeypatch
module-level names like `ReportService`/`pdf_service` directly on this
module object. A name reassigned via `monkeypatch.setattr(documents_routes,
"ReportService", ...)` only takes effect for code whose own global lookup
resolves against *this* module's namespace -- so `_ingest_document` (which
references `ReportService`) has to stay here, not in a submodule with its
own separate import of that name.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.schemas.financial import DocumentWithText, FinancialMetricsResponse
from app.services import investor_relations_client, period_merge_service  # noqa: F401 (investor_relations_client re-exported below for tests that monkeypatch it here)
from app.services.extraction_confidence import LowConfidenceExtractionError
from app.services.pdf_service import PDFExtractionService
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Shared PDF extraction service for upload and document processing flows.
pdf_service = PDFExtractionService()

# 20MB matches the only existing precedent in this repo
# (DELIVERY_READINESS_REPORT.md's original upload spec), which was never
# actually enforced anywhere until now -- FastAPI/Starlette impose no
# default request-body size limit on their own.
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


# ============================================================
# Helper
# ============================================================

def _effective_tier(tier: Optional[str], human_approved_at) -> Optional[str]:
    """
    The tier as shown to API consumers -- distinct from the raw, permanent
    `extraction_confidence_tier` column. A human-approved `needs_review` row
    reads as `auto_accept` everywhere it's *displayed* (no more "Pending
    Review" tag, since a human has confirmed it) without the underlying
    algorithmic score/tier ever being rewritten -- that stays an honest,
    unaltered record of what the extractor actually found. See
    FinancialMetrics.human_approved_at's own docstring for the full
    reasoning.
    """
    if human_approved_at is not None and tier == "needs_review":
        return "auto_accept"
    return tier


def build_document_response(
    doc: Document,
    report: Optional[Report] = None,
    metrics: Optional[FinancialMetrics] = None,
) -> DocumentWithText:

    financial_metrics = None

    if metrics:
        financial_metrics = FinancialMetricsResponse(
            id=metrics.id,
            document_id=metrics.document_id,
            revenue=metrics.revenue,
            customers=metrics.customers,
            cash=metrics.cash,
            ebitda=metrics.ebitda,
            gross_margin=metrics.gross_margin,
            operating_margin=metrics.operating_margin,
            extracted_at=metrics.extracted_at or doc.extracted_at,
            extraction_confidence=metrics.extraction_confidence,
            extraction_confidence_tier=_effective_tier(metrics.extraction_confidence_tier, metrics.human_approved_at),
            extraction_confidence_reasons=metrics.extraction_confidence_reasons,
        )

    return DocumentWithText(
        id=doc.id,
        filename=doc.filename,
        extracted_text=doc.extracted_text,
        status=doc.status,
        created_at=doc.created_at,
        extracted_at=doc.extracted_at,
        file_size=doc.file_size or 0,
        file_path=doc.file_path or "",
        report_id=report.id if report else None,
        financial_metrics=financial_metrics,
        superseded_by_document_id=metrics.superseded_by_document_id if metrics else None,
    )


async def _ingest_document(
    content: bytes,
    filename: str,
    db: AsyncSession,
    external_attachment_id: Optional[str] = None,
) -> DocumentWithText:
    """
    Shared by `upload_document` (manual upload) and `import_external_filing`
    (Senus investor-relations API import) -- everything from "we have valid
    PDF bytes and a filename" through extraction, dedup, report generation,
    and response building lives in exactly one place, so the two entry
    points can't drift out of sync.
    """
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB upload limit",
        )

    # Exact-duplicate detection: hash the raw bytes (not the filename --
    # a renamed copy of the same PDF should still match, and two
    # different PDFs that happen to share a filename shouldn't).
    content_hash = hashlib.sha256(content).hexdigest()
    existing = await db.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    duplicate = existing.scalars().first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This exact file was already uploaded as document "
                f"#{duplicate.id} on {duplicate.created_at:%Y-%m-%d}."
            ),
        )

    file_path, extracted_text = pdf_service.extract_text_from_upload(content, filename)

    document = Document(
        filename=filename,
        file_path=file_path,
        file_size=len(content),
        content_hash=content_hash,
        external_attachment_id=external_attachment_id,
        extracted_text=extracted_text,
        status="completed",
        created_at=datetime.utcnow(),
        extracted_at=datetime.utcnow(),
    )

    db.add(document)
    try:
        await db.flush()
    except IntegrityError:
        # Race: two imports/uploads of the same file (or the same IR
        # attachment_id) committed between the pre-check above and this
        # flush. The unique constraints are the real guarantee; the
        # pre-check is just the common-case fast path with a clearer
        # error message.
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This exact file was already uploaded (uploaded concurrently).",
        )

    report = None

    try:
        service = ReportService(db)
        report = await service.generate_report(document.id)
    except LowConfidenceExtractionError as e:
        # The Document/Report/FinancialMetrics rows are already durable at
        # this point -- `_generate` persists them (tier="rejected",
        # Report.status="rejected") before ever raising this, specifically
        # so a human can review *why* an extraction failed (the actual
        # attempted values, the confidence gate's own reasons) rather than
        # only ever seeing this one-time 422 message. Still 422s here for
        # the upload's own immediate feedback. Deliberately reverses this
        # project's original PR #42 policy of deleting a rejected
        # document's data outright -- that policy predates any UI capable
        # of showing a human the rejection reasons at all, which no longer
        # applies now that one exists (see the Documents page's "Rejected"
        # badge/review panel). It can never reach the dashboard either way
        # -- see `_generate`'s own comment on `_IS_CONFIDENT_ENOUGH_FOR_
        # DASHBOARD`.
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.warning(f"Report generation failed: {e}")

    await db.commit()

    metrics_result = await db.execute(
        select(FinancialMetrics)
        .where(FinancialMetrics.document_id == document.id)
        .order_by(FinancialMetrics.extracted_at.desc())
    )
    metrics = metrics_result.scalars().first()

    # A separate, additive follow-up step -- this document has already
    # finished ingesting completely and normally above, exactly as it does
    # today, regardless of what happens here. Only runs when this document's
    # own extraction succeeded well enough to know its reporting period at
    # all (see find_same_period_match). See period_merge_service's module
    # docstring for the real incident (ADF Farm Solutions vs. the
    # Information Document, both genuinely FY2025) this closes.
    if metrics is not None:
        existing_match = await period_merge_service.find_same_period_match(db, metrics)
        if existing_match is not None:
            await period_merge_service.merge_documents(db, existing_match, metrics)

    return build_document_response(document, report, metrics)


# Submodules import `router`/`_ingest_document`/`build_document_response`
# from this package and decorate directly onto the same `router` object
# (rather than each creating their own APIRouter() and being included via
# `router.include_router(...)`) -- FastAPI rejects a sub-router that's both
# prefix-less and has an empty-path route (`list_documents`'s `@router.get
# ("")`, needed so the combined path is exactly "/api/documents" with no
# trailing slash), so all three files share this one already-prefixed
# router instead. Imported after the definitions above so that, by the
# time Python executes `_core.py`/`_external_sync.py`'s own `from . import
# ...`, this (still-initializing) module already has those names bound --
# the standard pattern for resolving an otherwise-circular package/
# submodule dependency.
from . import _core, _external_sync  # noqa: E402, F401

# Re-exported because tests call these route handlers directly as plain
# functions (bypassing the FastAPI app/DI layer) via
# `from app.api.routes import documents as documents_routes` ->
# `documents_routes.upload_document(...)` etc. -- see this module's own
# docstring above.
from ._core import (  # noqa: E402, F401
    approve_document,
    delete_document,
    download_document_file,
    get_document,
    list_documents,
    reconcile_periods,
    upload_document,
)
from ._external_sync import (  # noqa: E402, F401
    hide_external_filing,
    import_external_filing,
    list_available_external_filings,
    list_hidden_external_filings,
    unhide_external_filing,
)

__all__ = [
    "router",
    "pdf_service",
    "investor_relations_client",
    "MAX_UPLOAD_SIZE_BYTES",
    "build_document_response",
    "upload_document",
    "get_document",
    "download_document_file",
    "approve_document",
    "reconcile_periods",
    "list_documents",
    "delete_document",
    "list_available_external_filings",
    "list_hidden_external_filings",
    "hide_external_filing",
    "unhide_external_filing",
    "import_external_filing",
]
