"""Financial metrics endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Metrics are always written internally by report generation
# (see ReportService._save_metrics) -- this router only reads them back
# for the dashboard. There is no client-facing metrics CRUD.


@router.get("/dashboard/summary")
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """
    Dashboard KPIs from FinancialMetrics table (latest + previous).
    """

    stmt = (
        select(FinancialMetrics)
        .order_by(FinancialMetrics.extracted_at.desc())
        .limit(2)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return {
            "revenue": {"value": "€0", "change": 0, "trend": "neutral"},
            "customers": {"value": "0", "change": 0, "trend": "neutral"},
            "cash": {"value": "€0", "change": 0, "trend": "neutral"},
            "ebitda": {"value": "€0", "change": 0, "trend": "neutral"},
        }

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None

    def change(curr, prev):
        return MetricsService.calculate_change(curr, prev)

    return {
        "revenue": {
            "value": MetricsService.format_currency(latest.revenue),
            "change": round(change(
                latest.revenue,
                previous.revenue if previous else None
            ), 1),
            "trend": MetricsService.get_trend(change(
                latest.revenue,
                previous.revenue if previous else None
            )),
        },
        "customers": {
            "value": f"{latest.customers:,}",
            "change": round(change(
                latest.customers,
                previous.customers if previous else None
            ), 1),
            "trend": MetricsService.get_trend(change(
                latest.customers,
                previous.customers if previous else None
            )),
        },
        "cash": {
            "value": MetricsService.format_currency(latest.cash),
            "change": round(change(
                latest.cash,
                previous.cash if previous else None
            ), 1),
            "trend": MetricsService.get_trend(change(
                latest.cash,
                previous.cash if previous else None
            )),
        },
        "ebitda": {
            "value": MetricsService.format_currency(latest.ebitda),
            "change": round(change(
                latest.ebitda,
                previous.ebitda if previous else None
            ), 1),
            "trend": MetricsService.get_trend(change(
                latest.ebitda,
                previous.ebitda if previous else None
            )),
        },
    }
