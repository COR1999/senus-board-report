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
    
    Process:
    1. Validate file (PDF only)
    2. Extract text using PyMuPDF
    3. Extract financial metrics using regex + optional Gemini AI
    4. Save document and metrics to database
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )

        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )

        logger.info(f"Processing document: {file.filename} ({len(content)} bytes)")

        # Extract text using PDF service
        try:
            file_path: str
            extracted_text: str
            file_path, extracted_text = pdf_service.extract_text_from_upload(
                content, 
                file.filename  # type: ignore
            )
            logger.info(f"PDF saved to: {file_path}")
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract text from PDF: {str(e)}"
            )

        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="No readable text found in PDF"
            )

        # Create document record
        document = Document(
            filename=file.filename,  # type: ignore
            extracted_text=extracted_text,
            status="processing",
            created_at=datetime.utcnow(),
        )
        
        db.add(document)
        await db.flush()
        document_id: int = document.id  # type: ignore

        logger.info(f"Document created with ID: {document_id}")

        # Extract metrics
        financial_metrics: FinancialMetrics | None = None
        try:
            metrics_dict = await gemini_service.extract_financial_metrics_from_text(
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
            logger.info(f"Financial metrics extracted: {metrics_dict}")

        except Exception as e:
            logger.warning(f"Metric extraction failed (non-critical): {e}")

        # Update document status
        document.status = "completed"  # type: ignore
        document.extracted_at = datetime.utcnow()  # type: ignore

        await db.commit()
        logger.info(f"Document {document_id} processing completed")

        # Build response
        metrics_response: FinancialMetricsResponse | None = None
        if financial_metrics:
            metrics_response = FinancialMetricsResponse(
                id=financial_metrics.id,  # type: ignore
                document_id=financial_metrics.document_id,  # type: ignore
                revenue=financial_metrics.revenue,  # type: ignore
                customers=financial_metrics.customers,  # type: ignore
                cash=financial_metrics.cash,  # type: ignore
                ebitda=financial_metrics.ebitda,  # type: ignore
                gross_margin=financial_metrics.gross_margin,  # type: ignore
                operating_margin=financial_metrics.operating_margin,  # type: ignore
                extracted_at=financial_metrics.extracted_at,  # type: ignore
            )

        return DocumentWithText(
            id=document.id,  # type: ignore
            filename=document.filename,  # type: ignore
            extracted_text=document.extracted_text,  # type: ignore
            status=document.status,  # type: ignore
            created_at=document.created_at,  # type: ignore
            extracted_at=document.extracted_at,  # type: ignore
            financial_metrics=metrics_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading document: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to process document"
        )


@router.get("/{document_id}", response_model=DocumentWithText)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentWithText:
    """Retrieve a document with extracted text and metrics."""
    try:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found"
            )

        # Fetch metrics
        metrics_result = await db.execute(
            select(FinancialMetrics).where(
                FinancialMetrics.document_id == document_id
            )
        )
        metrics = metrics_result.scalars().first()

        metrics_response: FinancialMetricsResponse | None = None
        if metrics:
            metrics_response = FinancialMetricsResponse(
                id=metrics.id,  # type: ignore
                document_id=metrics.document_id,  # type: ignore
                revenue=metrics.revenue,  # type: ignore
                customers=metrics.customers,  # type: ignore
                cash=metrics.cash,  # type: ignore
                ebitda=metrics.ebitda,  # type: ignore
                gross_margin=metrics.gross_margin,  # type: ignore
                operating_margin=metrics.operating_margin,  # type: ignore
                extracted_at=metrics.extracted_at,  # type: ignore
            )

        return DocumentWithText(
            id=document.id,  # type: ignore
            filename=document.filename,  # type: ignore
            extracted_text=document.extracted_text,  # type: ignore
            status=document.status,  # type: ignore
            created_at=document.created_at,  # type: ignore
            extracted_at=document.extracted_at,  # type: ignore
            financial_metrics=metrics_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve document"
        )


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
                select(FinancialMetrics).where(
                    FinancialMetrics.document_id == doc.id  # type: ignore
                )
            )
            metrics = metrics_result.scalars().first()

            metrics_response: FinancialMetricsResponse | None = None
            if metrics:
                metrics_response = FinancialMetricsResponse(
                    id=metrics.id,  # type: ignore
                    document_id=metrics.document_id,  # type: ignore
                    revenue=metrics.revenue,  # type: ignore
                    customers=metrics.customers,  # type: ignore
                    cash=metrics.cash,  # type: ignore
                    ebitda=metrics.ebitda,  # type: ignore
                    gross_margin=metrics.gross_margin,  # type: ignore
                    operating_margin=metrics.operating_margin,  # type: ignore
                    extracted_at=metrics.extracted_at,  # type: ignore
                )

            response.append(DocumentWithText(
                id=doc.id,  # type: ignore
                filename=doc.filename,  # type: ignore
                extracted_text=doc.extracted_text,  # type: ignore
                status=doc.status,  # type: ignore
                created_at=doc.created_at,  # type: ignore
                extracted_at=doc.extracted_at,  # type: ignore
                financial_metrics=metrics_response,
            ))

        return response

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list documents"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a document and associated metrics/reports."""
    try:
        # Delete metrics first (foreign key constraint)
        await db.execute(
            delete(FinancialMetrics).where(
                FinancialMetrics.document_id == document_id
            )
        )

        # Delete document
        result = await db.execute(
            delete(Document).where(Document.id == document_id)
        )

        if result.rowcount == 0:  # type: ignore
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        await db.commit()
        logger.info(f"Document {document_id} deleted")

        return {"message": f"Document {document_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document"
        )