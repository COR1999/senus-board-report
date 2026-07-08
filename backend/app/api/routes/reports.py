from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.models.report_insights import ReportInsights
from app.schemas.report import (
    ReportResponse,
    ReportDeleteResponse,
    ReportDashboardResponse,
    ReportInsightsUpsert,
    ReportInsightsResponse,
)
from app.services.report_service import ReportService
from app.services.extraction_confidence import LowConfidenceExtractionError

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
    except LowConfidenceExtractionError as exc:
        # `get_or_create_report` only ever reaches `_generate` for a
        # document with no prior report (`generate_report`'s default
        # `force=False`), so `persist_on_reject` is True -- `_generate`
        # itself already moved the Report from "generating" to a properly
        # finalized "rejected" (with the attempted FinancialMetrics/reasons
        # saved for review) before raising this, nothing left stuck to
        # clean up here.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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

    # Captured before attempting regeneration -- restored below on a
    # low-confidence rejection, since `generate_report` already commits
    # the report's status to "generating" *before* the confidence check
    # runs (see the comment in `generate_or_get_report` above), so a plain
    # `db.rollback()` cannot undo it.
    previous_status = report.status

    try:
        return await service.generate_report(report.document_id, force=True)
    except LowConfidenceExtractionError as exc:
        # A regenerate attempt that would produce worse data than what's
        # already there must not silently overwrite it -- the existing
        # FinancialMetrics/Report.summary/ai_commentary were never touched
        # (the rejection happens before `_save_metrics` runs), but the
        # Report's `status` was already committed to "generating" and must
        # be explicitly restored, not left stuck.
        stmt = select(Report).where(Report.id == report_id)
        result = await db.execute(stmt)
        stuck_report = result.scalars().first()
        if stuck_report is not None:
            stuck_report.status = previous_status
            stuck_report.updated_at = datetime.utcnow()
            await db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
async def delete_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a report by ID."""
    service = ReportService(db)
    success = await service.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"deleted": True}


@router.get("/{report_id}/insights", response_model=ReportInsightsResponse)
async def get_report_insights(report_id: int, db: AsyncSession = Depends(get_db)):
    """
    Stored AI Board Insights for a report, if a real (non-fallback)
    generation has ever succeeded and been persisted for it -- 404 means
    "never generated yet," not an error, so the frontend can generate fresh
    and persist the result via PUT below.
    """
    stmt = select(ReportInsights).where(ReportInsights.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="No insights stored for this report yet")
    return row


@router.put("/{report_id}/insights", response_model=ReportInsightsResponse)
async def save_report_insights(
    report_id: int, body: ReportInsightsUpsert, db: AsyncSession = Depends(get_db)
):
    """
    Upsert (create or replace) the stored insights for a report. The Gemini
    call itself stays entirely frontend-side -- this endpoint only ever
    persists what the frontend already generated, keeping the two Gemini
    integrations' quota pools exactly as separate as they are everywhere
    else in this project.
    """
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Report not found")

    stmt = select(ReportInsights).where(ReportInsights.report_id == report_id)
    result = await db.execute(stmt)
    row = result.scalars().first()

    insights_data = [insight.model_dump() for insight in body.insights]
    if row:
        row.insights = insights_data
        row.model_version = body.model_version
        row.generated_at = datetime.utcnow()
    else:
        row = ReportInsights(
            report_id=report_id,
            insights=insights_data,
            model_version=body.model_version,
            generated_at=datetime.utcnow(),
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return row


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