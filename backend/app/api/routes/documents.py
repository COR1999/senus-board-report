"""
Document upload and management endpoints.
Integrates PDF extraction with Report generation and FinancialMetrics system.
"""

import hashlib
import logging
from typing import List, Optional
from datetime import datetime

from pathlib import Path as FilePath

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.document import Document
from app.models.report import Report
from app.models.financial_metrics import FinancialMetrics
from app.models.hidden_external_filing import HiddenExternalFiling
from app.schemas.financial import (
    DocumentResponse,
    DocumentWithText,
    ExternalFilingSummary,
    FinancialMetricsResponse,
)
from app.services.pdf_service import PDFExtractionService
from app.services.report_service import ReportService
from app.services import investor_relations_client
from app.services.extraction_confidence import LowConfidenceExtractionError

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

    return build_document_response(document, report, metrics)


# ============================================================
# Upload
# ============================================================

@router.post("/upload", response_model=DocumentWithText)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):

    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        content = await file.read()
        return await _ingest_document(content, file.filename, db)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Upload failed")


# ============================================================
# Investor relations API sync
# ============================================================

@router.get("/external/available", response_model=List[ExternalFilingSummary])
async def list_available_external_filings(db: AsyncSession = Depends(get_db)):
    """
    Filings on Senus's investor relations API not yet in this system.
    Read-only -- doesn't download or ingest anything, just compares
    metadata so the frontend can show an "import?" prompt.
    """
    try:
        filings = await investor_relations_client.list_available_filings()
    except Exception as e:
        logger.error(f"Failed to reach investor relations API: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Could not reach the investor relations API")

    existing = await db.execute(select(Document.external_attachment_id, Document.filename))
    known_attachment_ids = set()
    known_filenames = set()
    for attachment_id, filename in existing.all():
        if attachment_id:
            known_attachment_ids.add(attachment_id)
        known_filenames.add(filename)

    hidden = await db.execute(select(HiddenExternalFiling.attachment_id))
    hidden_attachment_ids = {row[0] for row in hidden.all()}

    # Filtered by both attachment_id AND filename -- the real API has
    # already shown one edge case where the exact same filing (the
    # half-year results, manually uploaded here, so its
    # external_attachment_id is NULL) appears under two different
    # attachment_ids across different category listings. An
    # attachment_id-only check would wrongly flag it as "new" every time.
    # Also excludes anything the user has explicitly marked out of scope
    # (see /external/{attachment_id}/hide) -- a rejected import (422, low
    # confidence) creates no Document row by design, so without this
    # exclusion a governance filing the user has already reviewed and
    # dismissed would keep re-appearing here forever.
    return [
        ExternalFilingSummary(**f)
        for f in filings
        if f["attachment_id"] not in known_attachment_ids
        and f["file_name"] not in known_filenames
        and f["attachment_id"] not in hidden_attachment_ids
    ]


@router.get("/external/hidden", response_model=List[ExternalFilingSummary])
async def list_hidden_external_filings(db: AsyncSession = Depends(get_db)):
    """
    Filings the user has explicitly marked out of scope (see
    /external/{attachment_id}/hide) -- a secondary, out-of-the-way list so
    a dismissed non-financial filing (an AGM notice, Memo & Articles) can
    still be reviewed/restored later without permanently disappearing.
    """
    result = await db.execute(
        select(HiddenExternalFiling).order_by(HiddenExternalFiling.hidden_at.desc())
    )
    return [
        ExternalFilingSummary(
            attachment_id=row.attachment_id,
            file_name=row.file_name,
            file_size=row.file_size,
            published_date=row.published_date,
        )
        for row in result.scalars().all()
    ]


@router.post("/external/{attachment_id}/hide", response_model=ExternalFilingSummary)
async def hide_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Marks a filing as out of scope so it stops cluttering "available
    filings" -- for a document with no extractable financial data (a
    governance filing, or one that failed the confidence gate) that the
    user has already reviewed and doesn't want to keep seeing. Idempotent:
    hiding an already-hidden filing just returns it unchanged.
    """
    existing = await db.execute(
        select(HiddenExternalFiling).where(HiddenExternalFiling.attachment_id == attachment_id)
    )
    row = existing.scalars().first()
    if row is not None:
        return ExternalFilingSummary(
            attachment_id=row.attachment_id, file_name=row.file_name,
            file_size=row.file_size, published_date=row.published_date,
        )

    filing = await investor_relations_client.find_filing(attachment_id)
    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found on the investor relations API")

    row = HiddenExternalFiling(
        attachment_id=filing["attachment_id"],
        file_name=filing["file_name"],
        file_size=filing.get("file_size"),
        published_date=filing.get("published_date"),
    )
    db.add(row)
    await db.commit()

    return ExternalFilingSummary(
        attachment_id=row.attachment_id, file_name=row.file_name,
        file_size=row.file_size, published_date=row.published_date,
    )


@router.post("/external/{attachment_id}/unhide", status_code=204)
async def unhide_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    """Restores a hidden filing back to the "available" list. Idempotent."""
    existing = await db.execute(
        select(HiddenExternalFiling).where(HiddenExternalFiling.attachment_id == attachment_id)
    )
    row = existing.scalars().first()
    if row is not None:
        await db.delete(row)
        await db.commit()


@router.post("/external/{attachment_id}/import", response_model=DocumentWithText)
async def import_external_filing(attachment_id: str, db: AsyncSession = Depends(get_db)):
    try:
        filing = await investor_relations_client.find_filing(attachment_id)
        if filing is None:
            raise HTTPException(status_code=404, detail="Filing not found on the investor relations API")

        content = await investor_relations_client.download_filing(attachment_id)
        filename = filing["file_name"]
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"

        return await _ingest_document(content, filename, db, external_attachment_id=attachment_id)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"External filing import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Import failed")


# ============================================================
# Get document
# ============================================================

@router.get("/{document_id}", response_model=DocumentWithText)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.reports))
    )

    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    report = doc.reports[0] if doc.reports else None

    metrics_result = await db.execute(
        select(FinancialMetrics)
        .where(FinancialMetrics.document_id == document_id)
        .order_by(FinancialMetrics.extracted_at.desc())
    )
    metrics = metrics_result.scalars().first()

    return build_document_response(doc, report, metrics)


# ============================================================
# Download original file
# ============================================================

@router.get("/{document_id}/file")
async def download_document_file(document_id: int, db: AsyncSession = Depends(get_db)):
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Railway's filesystem is ephemeral (see backend/README.md) -- a
    # document uploaded before the most recent deploy/restart can have its
    # DB row and extracted text intact (Postgres persists independently)
    # while the raw PDF bytes on disk are gone. Distinguished from "document
    # not found" with a specific message, rather than a generic 404, so the
    # frontend/user isn't told the document itself doesn't exist.
    if not document.file_path or not FilePath(document.file_path).exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "The original PDF is no longer available on the server "
                "(uploads aren't yet persisted across deploys)."
            ),
        )

    return FileResponse(
        document.file_path,
        media_type="application/pdf",
        filename=document.filename,
    )


# ============================================================
# Human review (needs_review -> dashboard-eligible)
# ============================================================

@router.post("/{document_id}/approve", response_model=DocumentWithText)
async def approve_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    A human has reviewed a `needs_review` document's actual extracted
    values (the confidence gate's own reasons, or the source PDF via the
    existing "View source" link) and confirmed it's correct -- lets it
    start driving the executive dashboard's headline KPIs, the same as an
    `auto_accept` document, without silently rewriting the algorithmic
    score/tier that got it here (see FinancialMetrics.human_approved_at).

    Only meaningful for a `needs_review` document -- `auto_accept` never
    needed approval, and `rejected` was never persisted at all (nothing to
    approve). Both are a 400, not a silent no-op, so a stale UI state
    (e.g. a double-click) surfaces clearly rather than pretending to
    succeed at nothing.
    """
    result = await db.execute(
        select(FinancialMetrics).where(FinancialMetrics.document_id == document_id)
    )
    metrics = result.scalars().first()

    if metrics is None:
        raise HTTPException(status_code=404, detail="Document not found or has no extracted metrics")

    if metrics.extraction_confidence_tier != "needs_review":
        raise HTTPException(
            status_code=400,
            detail=(
                f"This document is not pending review (tier: "
                f"{metrics.extraction_confidence_tier or 'auto_accept'}) -- nothing to approve."
            ),
        )

    metrics.human_approved_at = datetime.utcnow()
    await db.commit()

    doc_result = await db.execute(
        select(Document).where(Document.id == document_id).options(selectinload(Document.reports))
    )
    doc = doc_result.scalars().first()
    report = doc.reports[0] if doc and doc.reports else None

    return build_document_response(doc, report, metrics)


# ============================================================
# List documents
# ============================================================

# The list view (a table of filename/status/size/date) never needs
# `extracted_text` (the full PDF text, tens of KB per document) or the
# financial_metrics/report_id detail that GET /{id} returns -- returning
# DocumentWithText for every row here sent that payload for no reason, and
# fetching FinancialMetrics to fill it in meant one extra query per
# document (an N+1: the exact pattern this codebase already avoids
# elsewhere, see metrics.py's _ai_reporting_periods_by_document). Neither
# is needed since DocumentResponse (filename/size/id/status/created_at) is
# already the frontend's DocumentItem shape.
@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = result.scalars().all()

    # A single batched query for extraction_confidence_tier, not one
    # per-document lookup -- same pattern as metrics.py's
    # _ai_reporting_periods_by_document, avoiding the exact N+1 this list
    # endpoint's own docstring above already had fixed once for
    # financial_metrics generally.
    tiers: dict[int, str] = {}
    if docs:
        tier_result = await db.execute(
            select(
                FinancialMetrics.document_id,
                FinancialMetrics.extraction_confidence_tier,
                FinancialMetrics.human_approved_at,
            ).where(FinancialMetrics.document_id.in_([doc.id for doc in docs]))
        )
        tiers = {
            document_id: effective
            for document_id, tier, human_approved_at in tier_result.all()
            if (effective := _effective_tier(tier, human_approved_at)) is not None
        }

    # Built explicitly (not left to FastAPI's automatic response_model
    # filtering) so the shape is real and testable by calling this function
    # directly, matching this codebase's established test pattern -- and so
    # it's unambiguous at a glance that extracted_text never leaves this
    # function, not just that it's dropped somewhere downstream.
    responses = []
    for doc in docs:
        response = DocumentResponse.model_validate(doc)
        response.extraction_confidence_tier = tiers.get(doc.id)
        responses.append(response)
    return responses


# ============================================================
# Delete
# ============================================================

@router.delete("/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    # A bulk `delete(Document).where(...)` statement issues a direct SQL
    # DELETE that bypasses the ORM-level `cascade="all, delete-orphan"` on
    # Document's relationships -- there's no DB-level ON DELETE CASCADE
    # foreign key, so that used to fail with a ForeignKeyViolationError on
    # any document that actually had FinancialMetrics/BalanceSheetMetrics/
    # Report rows attached (i.e. any successfully processed document, the
    # common case). Loading the instance and deleting it through the
    # session lets the ORM cascade fire correctly.
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.delete(document)
    await db.commit()

    return {"message": "Deleted successfully"}
