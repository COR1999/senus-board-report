"""
GET/PUT /metrics/dashboard/historical-insight -- the persisted AI insight
describing the trend across every report on file (distinct from the
per-report AI Board Insights in reports.py).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.historical_insight import HistoricalInsight
from app.schemas import HistoricalInsightResponse, HistoricalInsightUpsert

from ._shared import _chart_data_fingerprint
from .charts import get_revenue_trend

router = APIRouter()


@router.get("/dashboard/historical-insight", response_model=HistoricalInsightResponse)
async def get_historical_insight(db: AsyncSession = Depends(get_db)):
    """
    The stored AI insight describing the trend across every report on file,
    if one has been generated for the CURRENT all-reports data set -- 404
    both when nothing's ever been generated, and when the underlying chart
    data has changed since the stored insight was generated (its
    `data_fingerprint` no longer matches), so the frontend knows to
    regenerate either way rather than showing a stale trend description.
    """
    current_points = await get_revenue_trend(db)
    current_fingerprint = _chart_data_fingerprint(current_points)

    stmt = select(HistoricalInsight).order_by(HistoricalInsight.generated_at.desc())
    result = await db.execute(stmt)
    row = result.scalars().first()

    if not row or row.data_fingerprint != current_fingerprint:
        raise HTTPException(status_code=404, detail="No up-to-date historical insight stored yet")
    return row


@router.put("/dashboard/historical-insight", response_model=HistoricalInsightResponse)
async def save_historical_insight(body: HistoricalInsightUpsert, db: AsyncSession = Depends(get_db)):
    """
    Upsert (create or replace) the stored historical-trend insight, stamped
    with a fingerprint of the CURRENT all-reports chart data -- computed
    server-side, never trusted from the client, so a stale/mismatched
    fingerprint can never be persisted as if it were current. The Gemini call
    itself stays entirely frontend-side, same as the per-report insights --
    this endpoint only ever persists what the frontend already generated.
    """
    current_points = await get_revenue_trend(db)
    current_fingerprint = _chart_data_fingerprint(current_points)

    stmt = select(HistoricalInsight).order_by(HistoricalInsight.generated_at.desc())
    result = await db.execute(stmt)
    row = result.scalars().first()

    insight_data = body.insight.model_dump()
    if row:
        row.insight = insight_data
        row.data_fingerprint = current_fingerprint
        row.model_version = body.model_version
        row.generated_at = datetime.utcnow()
    else:
        row = HistoricalInsight(
            insight=insight_data,
            data_fingerprint=current_fingerprint,
            model_version=body.model_version,
            generated_at=datetime.utcnow(),
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return row
