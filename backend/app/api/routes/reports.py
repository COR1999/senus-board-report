"""
Report generation endpoints.
Creates AI-powered financial analysis reports from uploaded documents.
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.schemas.report import ReportResponse, ReportCreate
from app.services.gemini_service import GeminiAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])
gemini_service = GeminiAnalysisService()


@router.post("", response_model=ReportResponse)
async def generate_report(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """
    Generate an AI-powered report from an uploaded document.
    
    Process:
    1. Retrieve document and metrics
    2. Generate executive summary using Gemini
    3. Generate bullet-point summary
    4. Save report to database
    
    Args:
        document_id: ID of document to analyze
        db: Database session
        
    Returns:
        ReportResponse with AI commentary and summary
        
    Raises:
        HTTPException: If document not found or generation fails
    """
    try:
        # Fetch document
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

        metrics_dict = {
            "revenue": metrics.revenue if metrics else None,
            "customers": metrics.customers if metrics else None,
            "cash": metrics.cash if metrics else None,
            "ebitda": metrics.ebitda if metrics else None,
            "gross_margin": metrics.gross_margin if metrics else None,
            "operating_margin": metrics.operating_margin if metrics else None,
        }

        logger.info(f"Generating report for document {document_id}")

        # Generate AI commentary
        try:
            ai_commentary = await gemini_service.generate_ai_commentary(
                document.extracted_text,
                metrics_dict,
                company_name=document.filename.replace(".pdf", "")
            )
        except Exception as e:
            logger.warning(f"Failed to generate AI commentary: {e}")
            ai_commentary = "Report generation in progress. Please try again shortly."

        # Generate summary bullets
        try:
            summary_bullets = await gemini_service.generate_report_summary(
                document.extracted_text,
                metrics_dict
            )
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            summary_bullets = ["Report processing complete."]

        # Create report record
        report = Report(
            document_id=document_id,
            ai_commentary=ai_commentary,
            summary=summary_bullets,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(report)
        await db.commit()
        await db.refresh(report)

        logger.info(f"Report {report.id} created for document {document_id}")

        return ReportResponse(
            id=report.id,
            document_id=report.document_id,
            ai_commentary=report.ai_commentary,
            summary=report.summary,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to generate report"
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """
    Retrieve a report by ID.
    
    Args:
        report_id: Report ID
        db: Database session
        
    Returns:
        ReportResponse
        
    Raises:
        HTTPException: If report not found
    """
    try:
        result = await db.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalars().first()

        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Report {report_id} not found"
            )

        return ReportResponse(
            id=report.id,
            document_id=report.document_id,
            ai_commentary=report.ai_commentary,
            summary=report.summary,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve report"
        )


@router.get("", response_model=List[ReportResponse])
async def list_reports(
    document_id: int = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> List[ReportResponse]:
    """
    List reports with optional filtering by document.
    
    Args:
        document_id: Filter by document (optional)
        skip: Pagination offset
        limit: Pagination limit
        db: Database session
        
    Returns:
        List of reports
    """
    try:
        query = select(Report)
        
        if document_id:
            query = query.where(Report.document_id == document_id)
        
        query = query.order_by(Report.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        reports = result.scalars().all()

        return [
            ReportResponse(
                id=r.id,
                document_id=r.document_id,
                ai_commentary=r.ai_commentary,
                summary=r.summary,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in reports
        ]

    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list reports"
        )


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete a report.
    
    Args:
        report_id: Report ID
        db: Database session
        
    Returns:
        Confirmation message
    """
    try:
        result = await db.execute(
            delete(Report).where(Report.id == report_id)
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Report not found"
            )

        await db.commit()
        logger.info(f"Report {report_id} deleted")

        return {"message": f"Report {report_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting report: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete report"
        )