"""Financial metrics endpoints."""
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.services.metrics_service import MetricsService
from app.schemas import DashboardSummaryResponse, KPIMetric

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Metrics are always written internally by report generation
# (see ReportService._save_metrics) -- this router only reads them back
# for the dashboard. There is no client-facing metrics CRUD.

# Number of most-recent FinancialMetrics rows (one per uploaded document)
# to expose as sparkline history. Not calendar-aware -- see
# backend/docs/metrics-expansion-plan.md section 5 for the known gap
# around "latest two uploads" vs. true calendar-period comparisons.
HISTORY_WINDOW = 8


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """
    Dashboard KPIs from FinancialMetrics table (latest + previous),
    plus up to HISTORY_WINDOW historical points per KPI for sparklines.
    """

    stmt = (
        select(FinancialMetrics)
        .order_by(FinancialMetrics.extracted_at.desc())
        .limit(HISTORY_WINDOW)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        empty = KPIMetric(value="€0", change=0, trend="neutral", history=[])
        empty_count = KPIMetric(value="0", change=0, trend="neutral", history=[])
        return DashboardSummaryResponse(
            revenue=empty, customers=empty_count, cash=empty, ebitda=empty,
        )

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None

    def history(field: str) -> List[Optional[float]]:
        # Oldest -> newest. None means the document didn't report this field --
        # never coerce to 0.0 (see backend/docs/metrics-expansion-plan.md's
        # "missing-vs-zero" convention; this table already had that bug fixed once).
        return [
            (float(v) if (v := getattr(r, field)) is not None else None)
            for r in reversed(rows)
        ]

    def build(field: str, formatter: Callable[[Optional[float]], str]) -> KPIMetric:
        curr_val = getattr(latest, field)
        prev_val = getattr(previous, field) if previous else None
        pct_change = round(MetricsService.calculate_change(curr_val, prev_val), 1)
        return KPIMetric(
            value=formatter(curr_val),
            change=pct_change,
            trend=MetricsService.get_trend(pct_change),
            history=history(field),
        )

    return DashboardSummaryResponse(
        revenue=build("revenue", MetricsService.format_currency),
        customers=build("customers", lambda v: f"{int(v or 0):,}"),
        cash=build("cash", MetricsService.format_currency),
        ebitda=build("ebitda", MetricsService.format_currency),
    )
