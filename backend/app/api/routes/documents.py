"""
Document upload and management endpoints.
Integrates PDF extraction with Report generation and FinancialMetrics system.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.document import Document
from app.models.report import Report
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import DocumentWithText, FinancialMetricsResponse
from app.services.pdf_service import PDFExtractionService
from app.services.report_service import ReportService  # ✅ FIXED IMPORT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

pdf_service = PDFExtractionService()


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
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")

        file_path, extracted_text = pdf_service.extract_text_from_upload(
            content, file.filename
        )

        document = Document(
            filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            extracted_text=extracted_text,
            status="completed",
            created_at=datetime.utcnow(),
            extracted_at=datetime.utcnow(),
        )

        db.add(document)
        await db.flush()

        report = None

        try:
            service = ReportService(db)
            report = await service.generate_report(document.id)
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
# List documents
# ============================================================

@router.get("", response_model=List[DocumentWithText])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Document)
        .options(selectinload(Document.reports))
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    docs = result.scalars().all()

    responses = []
    for doc in docs:
        metrics_result = await db.execute(
            select(FinancialMetrics)
            .where(FinancialMetrics.document_id == doc.id)
            .order_by(FinancialMetrics.extracted_at.desc())
        )
        metrics = metrics_result.scalars().first()
        responses.append(
            build_document_response(
                doc,
                doc.reports[0] if doc.reports else None,
                metrics,
            )
        )

    return responses


# ============================================================
# Delete
# ============================================================

@router.delete("/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        delete(Document).where(Document.id == document_id)
    )

    deleted_rows = getattr(result, "rowcount", 0)
    if deleted_rows == 0:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.commit()

    return {"message": "Deleted successfully"}


# ============================================================
# Regenerate report
# ============================================================

@router.post("/{document_id}/regenerate-report")
async def regenerate_report(document_id: int, db: AsyncSession = Depends(get_db)):

    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )

    document = doc_result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    service = ReportService(db)
    report = await service.generate_report(document_id, force=True)

    metrics_result = await db.execute(
        select(FinancialMetrics)
        .where(FinancialMetrics.document_id == document_id)
        .order_by(FinancialMetrics.extracted_at.desc())
    )

    metrics = metrics_result.scalars().first()

    return {
        "report_id": report.id,
        "status": report.status,
        "ai_commentary": report.ai_commentary,
        "key_findings": report.key_findings,
        "financial_metrics": metrics.__dict__ if metrics else {},
    }