"""
Document upload and management endpoints.
Integrates PDF extraction with Gemini AI for metric extraction.
"""

import logging
from typing import List
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import DocumentWithText, FinancialMetricsResponse
from app.services.pdf_service import PDFExtractionService
from app.services.gemini_service import GeminiAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize services
pdf_service = PDFExtractionService()
gemini_service = GeminiAnalysisService()


@router.post("/upload", response_model=DocumentWithText)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentWithText:
    """
    Upload a PDF document and extract text and financial metrics.
    """
    file_path_var: str = ""

    try:
        # 1. Validate file
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")

        logger.info(f"Processing document: {file.filename} ({len(content)} bytes)")

        # 2. Extract text from PDF
        try:
            file_path_var, extracted_text = pdf_service.extract_text_from_upload(
                content, file.filename
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to extract text from PDF: {str(e)}"
            )

        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No readable text found in PDF")

        # 3. Create Document record
        document = Document(
            filename=file.filename,
            file_path=file_path_var,
            file_size=len(content),
            extracted_text=extracted_text,
            status="processing",
            created_at=datetime.utcnow(),
        )
        db.add(document)
        await db.flush()

        document_id = document.id

        # 4. Extract financial metrics
        financial_metrics = None
        try:
            metrics_dict = await gemini_service.extract_financial_metrics_from_text(
                extracted_text, use_ai=gemini_service.is_available()
            )

            financial_metrics = FinancialMetrics(
                document_id=document_id,
                revenue=metrics_dict.get("revenue"),
                customers=metrics_dict.get("customers"),
                cash=metrics_dict.get("cash"),
                ebitda=metrics_dict.get("ebitda"),
                gross_margin=metrics_dict.get("gross_margin"),
                operating_margin=metrics_dict.get("operating_margin"),
                extracted_at=datetime.utcnow(),
            )
            db.add(financial_metrics)

        except Exception as e:
            logger.warning(f"Metric extraction failed (non-critical): {e}")

        # 5. Update document
        document.status = "completed"
        document.extracted_at = datetime.utcnow()

        await db.commit()
        logger.info(f"Document {document_id} processing completed")

        # 6. Build metrics response
        metrics_response = None
        if financial_metrics:
            metrics_response = FinancialMetricsResponse(
                id=financial_metrics.id,
                document_id=financial_metrics.document_id,
                revenue=financial_metrics.revenue,
                customers=financial_metrics.customers,
                cash=financial_metrics.cash,
                ebitda=financial_metrics.ebitda,
                gross_margin=financial_metrics.gross_margin,
                operating_margin=financial_metrics.operating_margin,
                extracted_at=financial_metrics.extracted_at,
            )

        # 7. Return response
        return DocumentWithText(
            id=document.id,
            filename=document.filename,
            extracted_text=document.extracted_text,
            status=document.status,
            created_at=document.created_at,
            extracted_at=document.extracted_at,
            financial_metrics=metrics_response,
            file_size=document.file_size or len(content),
            file_path=document.file_path or file_path_var,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading document: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process document")


@router.get("/{document_id}", response_model=DocumentWithText)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentWithText:
    """Retrieve a document with extracted text and metrics."""
    try:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document {document_id} not found"
            )

        metrics_result = await db.execute(
            select(FinancialMetrics).where(FinancialMetrics.document_id == document_id)
        )
        metrics = metrics_result.scalars().first()

        metrics_response = None
        if metrics:
            metrics_response = FinancialMetricsResponse(
                id=metrics.id,
                document_id=metrics.document_id,
                revenue=metrics.revenue,
                customers=metrics.customers,
                cash=metrics.cash,
                ebitda=metrics.ebitda,
                gross_margin=metrics.gross_margin,
                operating_margin=metrics.operating_margin,
                extracted_at=metrics.extracted_at,
            )

        return DocumentWithText(
            id=document.id,
            filename=document.filename,
            extracted_text=document.extracted_text,
            status=document.status,
            created_at=document.created_at,
            extracted_at=document.extracted_at,
            financial_metrics=metrics_response,
            file_size=document.file_size or 0,
            file_path=document.file_path or "",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")


@router.get("", response_model=List[DocumentWithText])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> List[DocumentWithText]:
    """List all uploaded documents with pagination."""
    try:
        result = await db.execute(
            select(Document)
            .offset(skip)
            .limit(limit)
            .order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()

        response: List[DocumentWithText] = []
        for doc in documents:
            metrics_result = await db.execute(
                select(FinancialMetrics).where(FinancialMetrics.document_id == doc.id)
            )
            metrics = metrics_result.scalars().first()

            metrics_response = None
            if metrics:
                metrics_response = FinancialMetricsResponse(
                    id=metrics.id,
                    document_id=metrics.document_id,
                    revenue=metrics.revenue,
                    customers=metrics.customers,
                    cash=metrics.cash,
                    ebitda=metrics.ebitda,
                    gross_margin=metrics.gross_margin,
                    operating_margin=metrics.operating_margin,
                    extracted_at=metrics.extracted_at,
                )

            response.append(
                DocumentWithText(
                    id=doc.id,
                    filename=doc.filename,
                    extracted_text=doc.extracted_text,
                    status=doc.status,
                    created_at=doc.created_at,
                    extracted_at=doc.extracted_at,
                    financial_metrics=metrics_response,
                    file_size=doc.file_size or 0,
                    file_path=doc.file_path or "",
                )
            )

        return response

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")
@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a document and associated metrics/reports."""
    try:
        # Delete associated financial metrics first
        await db.execute(
            delete(FinancialMetrics).where(FinancialMetrics.document_id == document_id)
        )

        # Delete the document
        result = await db.execute(
            delete(Document).where(Document.id == document_id)
        )

        # ✅ Safe way to check if anything was deleted (Pylance friendly)
        rows_deleted = getattr(result, "rowcount", 0) or 0

        if rows_deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        await db.commit()
        logger.info(f"Document {document_id} deleted")
        return {"message": f"Document {document_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete document")