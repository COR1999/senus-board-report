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
            extraction_confidence_tier=metrics.extraction_confidence_tier,
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
        # Nothing about this document is trustworthy enough to keep. A
        # plain `db.rollback()` here is NOT enough: `generate_report`
        # already committed the initial "pending" Report row (and, via
        # that same commit, the Document row flushed above) before
        # `_generate` ever reaches the confidence check -- both are
        # already durable by this point, confirmed by testing, not
        # assumed. Deleting the Document explicitly cascades to its
        # Report/FinancialMetrics/BalanceSheetMetrics rows (see the
        # `cascade="all, delete-orphan"` relationships on Document), so a
        # rejected document leaves no trace at all (see
        # extraction_confidence.py's module docstring for the incident
        # this closes).
        await db.delete(document)
        await db.commit()
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

    # Filtered by both attachment_id AND filename -- the real API has
    # already shown one edge case where the exact same filing (the
    # half-year results, manually uploaded here, so its
    # external_attachment_id is NULL) appears under two different
    # attachment_ids across different category listings. An
    # attachment_id-only check would wrongly flag it as "new" every time.
    return [
        ExternalFilingSummary(**f)
        for f in filings
        if f["attachment_id"] not in known_attachment_ids and f["file_name"] not in known_filenames
    ]


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
            select(FinancialMetrics.document_id, FinancialMetrics.extraction_confidence_tier).where(
                FinancialMetrics.document_id.in_([doc.id for doc in docs])
            )
        )
        tiers = {document_id: tier for document_id, tier in tier_result.all() if tier is not None}

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
