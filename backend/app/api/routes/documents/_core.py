"""
Core document lifecycle endpoints: upload, get, list, delete, download the
original file, human review/approve, and period reconciliation. The
investor-relations sync endpoints live in `_external_sync.py` instead.
"""
import logging
from datetime import datetime
from pathlib import Path as FilePath
from typing import List, Optional

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import DocumentResponse, DocumentWithText
from app.services import period_merge_service

from . import _effective_tier, _ingest_document, build_document_response, router

logger = logging.getLogger(__name__)


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
# Period reconciliation (same-period duplicate documents)
# ============================================================

@router.post("/reconcile-periods", response_model=List[DocumentResponse])
async def reconcile_periods(db: AsyncSession = Depends(get_db)):
    """
    One-off (but safe to call repeatedly -- see period_merge_service's
    `reconcile_all_periods`) sweep for documents that independently report
    the exact same reporting period, merging each pair into a new combined
    document. Ingest-time merging (see `_ingest_document`) already prevents
    this for every future upload; this endpoint is for documents that
    existed before that existed, or before their period fields were
    derivable at all (e.g. a vision-extracted document uploaded before the
    cadence-detection fix). Returns the newly-created merged documents --
    an empty list means nothing needed merging.
    """
    merged_documents = await period_merge_service.reconcile_all_periods(db)

    # A single batched query for extraction_confidence_tier, not one
    # per-document lookup -- same pattern as list_documents just below,
    # avoiding the exact N+1 that endpoint's own docstring already
    # documents having fixed once for this table generally.
    tiers: dict[int, Optional[str]] = {}
    if merged_documents:
        tier_result = await db.execute(
            select(FinancialMetrics.document_id, FinancialMetrics.extraction_confidence_tier).where(
                FinancialMetrics.document_id.in_([doc.id for doc in merged_documents])
            )
        )
        tiers = dict(tier_result.all())

    responses = []
    for doc in merged_documents:
        response = DocumentResponse.model_validate(doc)
        response.extraction_confidence_tier = tiers.get(doc.id)
        responses.append(response)
    return responses


# ============================================================
# List documents
# ============================================================

# The list view (a table of filename/status/size/date) never needs
# `extracted_text` (the full PDF text, tens of KB per document) or the
# financial_metrics/report_id detail that GET /{id} returns -- returning
# DocumentWithText for every row here sent that payload for no reason, and
# fetching FinancialMetrics to fill it in meant one extra query per
# document (an N+1: the exact pattern this codebase already avoids
# elsewhere, see metrics/_shared.py's _ai_reporting_periods_by_document).
# Neither is needed since DocumentResponse (filename/size/id/status/
# created_at) is already the frontend's DocumentItem shape.
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
    # per-document lookup -- same pattern as metrics/_shared.py's
    # _ai_reporting_periods_by_document, avoiding the exact N+1 this list
    # endpoint's own docstring above already had fixed once for
    # financial_metrics generally.
    tiers: dict[int, str] = {}
    superseded_by: dict[int, int] = {}
    if docs:
        tier_result = await db.execute(
            select(
                FinancialMetrics.document_id,
                FinancialMetrics.extraction_confidence_tier,
                FinancialMetrics.human_approved_at,
                FinancialMetrics.superseded_by_document_id,
            ).where(FinancialMetrics.document_id.in_([doc.id for doc in docs]))
        )
        rows = tier_result.all()
        tiers = {
            document_id: effective
            for document_id, tier, human_approved_at, _ in rows
            if (effective := _effective_tier(tier, human_approved_at)) is not None
        }
        superseded_by = {
            document_id: merged_into
            for document_id, _, _, merged_into in rows
            if merged_into is not None
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
        response.superseded_by_document_id = superseded_by.get(doc.id)
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
