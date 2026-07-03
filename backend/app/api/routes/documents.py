"""
Document upload and management endpoints.
Integrates PDF extraction with Gemini AI for metric extraction.
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
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import DocumentWithText, FinancialMetricsResponse
from app.services.pdf_service import PDFExtractionService
from app.services.gemini_service import GeminiAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize services
pdf_service = PDFExtractionService()
gemini_service = GeminiAnalysisService()


# ==================== Helper Functions ====================
def build_metrics_response(metrics: Optional[FinancialMetrics]) -> Optional[FinancialMetricsResponse]:
    """Convert FinancialMetrics model to response schema."""
    if not metrics:
        return None
    
    return FinancialMetricsResponse(
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


def build_document_response(
    doc: Document, 
    metrics: Optional[FinancialMetrics] = None
) -> DocumentWithText:
    """Convert Document + FinancialMetrics to response schema."""
    return DocumentWithText(
        id=doc.id,
        filename=doc.filename,
        extracted_text=doc.extracted_text,
        status=doc.status,
        created_at=doc.created_at,
        extracted_at=doc.extracted_at,
        financial_metrics=build_metrics_response(metrics),
        file_size=doc.file_size or 0,
        file_path=doc.file_path or "",
    )


# ==================== Endpoints ====================

@router.post("/upload", response_model=DocumentWithText)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DocumentWithText:
    """
    Upload a PDF document and extract text and financial metrics.
    
    **Process:**
    1. Validate file (must be PDF)
    2. Extract text using PyMuPDF
    3. Create Document record with status "processing"
    4. Extract financial metrics using Gemini
    5. Update document status to "completed"
    
    **Returns:**
    - DocumentWithText with extracted text and metrics
    
    **Raises:**
    - 400: Invalid file type or empty file
    - 500: Processing failed
    """
    try:
        # 1. Validate file
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")

        logger.info(f"Processing document: {file.filename} ({len(content)} bytes)")

        # 2. Extract text from PDF (sync operation - fine for blocking)
        try:
            file_path, extracted_text = pdf_service.extract_text_from_upload(
                content, file.filename
            )
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to extract text from PDF: {str(e)}"
            )

        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No readable text found in PDF")

        # 3. Create Document record
        document = Document(
            filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            extracted_text=extracted_text,
            status="processing",
            created_at=datetime.utcnow(),
        )
        db.add(document)
        await db.flush()  # Get the ID without committing yet

        document_id = document.id

        # 4. Extract financial metrics (non-critical, don't fail if this fails)
        financial_metrics = None
        try:
            metrics_dict =  gemini_service.extract_financial_metrics_from_text(
                extracted_text, 
                use_ai=gemini_service.is_available()
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
            logger.info(f"Financial metrics extracted for document {document_id}")

        except Exception as e:
            logger.warning(f"Metric extraction failed (non-critical): {e}")
            # Don't raise - document is still valid without metrics

        # 5. Update document status
        document.status = "completed"
        document.extracted_at = datetime.utcnow()

        await db.commit()
        logger.info(f"Document {document_id} processing completed")

        # 6. Return response
        return build_document_response(document, financial_metrics)

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
    """
    Retrieve a document with extracted text and metrics.
    
    **Args:**
    - `document_id`: Document ID
    
    **Returns:**
    - DocumentWithText
    
    **Raises:**
    - 404: Document not found
    """
    try:
        # Fetch document with eager-loaded metrics (prevents N+1)
        result = await db.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.financial_metrics))
        )
        document = result.unique().scalars().first()

        if not document:
            raise HTTPException(
                status_code=404, 
                detail=f"Document {document_id} not found"
            )

        metrics = document.financial_metrics if hasattr(document, 'financial_metrics') else None
        return build_document_response(document, metrics)

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
    """
    List all uploaded documents with pagination.
    
    **Query Parameters:**
    - `skip`: Offset (default: 0)
    - `limit`: Max results (default: 20, max: 100)
    
    **Returns:**
    - List of DocumentWithText
    
    **Note:** Uses eager loading to avoid N+1 queries
    """
    try:
        # Use eager loading to prevent N+1 query problem
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.financial_metrics))
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        documents = result.unique().scalars().all()

        return [
            build_document_response(doc, doc.financial_metrics)
            for doc in documents
        ]

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete a document and associated metrics.
    
    **Args:**
    - `document_id`: Document ID
    
    **Returns:**
    - Confirmation message
    
    **Raises:**
    - 404: Document not found
    - 500: Deletion failed
    
    **Note:** Cascading deletes are handled by the database FK constraint.
    """
    try:
        # Delete document (metrics will cascade delete if FK has ondelete="CASCADE")
        result = await db.execute(
            delete(Document).where(Document.id == document_id)
        )

        # Pylance-friendly way to check rowcount
        rows_deleted = getattr(result, "rowcount", 0) or 0

        if rows_deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        await db.commit()
        logger.info(f"Document {document_id} and associated metrics deleted")
        return {"message": f"Document {document_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete document")