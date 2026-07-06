from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.schemas.report import (
    ReportResponse,
    ReportDeleteResponse,
    ReportDashboardResponse,
)
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Report endpoints support report creation, retrieval, regeneration, and dashboard payloads.


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Fetch a report by ID."""
    service = ReportService(db)
    report = await service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("", response_model=List[ReportResponse])
async def list_reports(db: AsyncSession = Depends(get_db)):
    """List all reports, most recent first."""
    service = ReportService(db)
    return await service.list_reports()


@router.get("/document/{document_id}", response_model=List[ReportResponse])
async def list_reports_for_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Get the report for a document (a document has at most one report)."""
    service = ReportService(db)
    return await service.list_reports(document_id=document_id)


@router.post("/document/{document_id}", response_model=ReportResponse)
async def generate_or_get_report(document_id: int, db: AsyncSession = Depends(get_db)):
    """Generate or retrieve a report for a document."""
    try:
        service = ReportService(db)
        return await service.get_or_create_report(document_id)
    except Exception as exc:
        logger.error("Error generating report: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{report_id}/regenerate", response_model=ReportResponse)
async def regenerate_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Force regenerate an existing report."""
    service = ReportService(db)
    report = await service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return await service.generate_report(report.document_id, force=True)


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
async def delete_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a report by ID."""
    service = ReportService(db)
    success = await service.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": True}


@router.get("/{report_id}/dashboard", response_model=ReportDashboardResponse)
async def get_dashboard_data(report_id: int, db: AsyncSession = Depends(get_db)):
    try:
        service = ReportService(db)
        report = await service.get_report(report_id)

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        stmt = (
            select(FinancialMetrics)
            .where(FinancialMetrics.document_id == report.document_id)
            .order_by(FinancialMetrics.extracted_at.desc())
        )

        result = await db.execute(stmt)
        metrics = result.scalars().first()

        return {
            "report_id": report.id,
            "document": {
                "id": report.document_id,
                "name": report.document.filename if report.document else "Unknown",
            },
            "financial_metrics": {
                "revenue": metrics.revenue if metrics else 0,
                "customers": metrics.customers if metrics else 0,
                "cash": metrics.cash if metrics else 0,
                "ebitda": metrics.ebitda if metrics else 0,
                "gross_margin": metrics.gross_margin if metrics else 0,
                "operating_margin": metrics.operating_margin if metrics else 0,
            },
            "key_findings": report.key_findings or [],
            "ai_commentary": report.ai_commentary,
            "generated_at": report.created_at,
            "model": report.model_version,
        }

    except Exception:
        logger.exception("Dashboard endpoint failed")
        raise