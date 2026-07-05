"""Financial metrics endpoints."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import (
    FinancialMetricsResponse,
    FinancialMetricsCreate
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# ---------------------------
# Helpers
# ---------------------------

def format_currency(amount: float | None, currency: str = "EUR") -> str:
    """Format amount as currency string."""
    if amount is None:
        return f"{currency} 0"

    symbol = "€" if currency.upper() == "EUR" else "$"

    if amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{symbol}{amount / 1_000:.0f}K"
    return f"{symbol}{amount:.0f}"


def get_trend(change: float) -> str:
    return "up" if change > 0 else "down" if change < 0 else "neutral"


def calc_change(current: float, previous: float | None) -> float:
    if not previous or previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


# ---------------------------
# Endpoints
# ---------------------------

@router.get("", response_model=list[FinancialMetricsResponse])
async def get_all_metrics(db: AsyncSession = Depends(get_db)):
    """Get all financial metrics."""
    stmt = select(FinancialMetrics).order_by(
        FinancialMetrics.extracted_at.desc()
    )
    result = await db.execute(stmt)
    metrics = result.scalars().all()

    return [
        FinancialMetricsResponse.model_validate(m)
        for m in metrics
    ]


@router.get("/{document_id}", response_model=FinancialMetricsResponse)
async def get_metrics_by_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get latest metrics for a document."""
    stmt = (
        select(FinancialMetrics)
        .where(FinancialMetrics.document_id == document_id)
        .order_by(FinancialMetrics.extracted_at.desc())
    )

    result = await db.execute(stmt)
    metrics = result.scalars().first()

    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found")

    return FinancialMetricsResponse.model_validate(metrics)


@router.post("", response_model=FinancialMetricsResponse)
async def create_metrics(
    metrics_data: FinancialMetricsCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create or update metrics for a document."""

    document_stmt = select(Document).where(Document.id == metrics_data.document_id)
    document_result = await db.execute(document_stmt)
    document = document_result.scalars().first()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    stmt = select(FinancialMetrics).where(
        FinancialMetrics.document_id == metrics_data.document_id
    )
    result = await db.execute(stmt)
    metrics = result.scalars().first()

    if metrics is None:
        metrics = FinancialMetrics(**metrics_data.model_dump())
        db.add(metrics)
    else:
        for key, value in metrics_data.model_dump(exclude={"document_id"}).items():
            setattr(metrics, key, value)

    metrics.extracted_at = datetime.utcnow()
    await db.commit()
    await db.refresh(metrics)

    return FinancialMetricsResponse.model_validate(metrics)


@router.get("/report/{report_id}/detailed")
async def get_detailed_metrics(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fully migrated version:
    Uses FinancialMetrics as source of truth.
    """

    from sqlalchemy import select
    from app.models.report import Report
    from app.models.financial_metrics import FinancialMetrics

    # 1. Get report
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # 2. Get latest financial metrics for this report
    stmt = (
        select(FinancialMetrics)
        .where(FinancialMetrics.document_id == report.document_id)
        .order_by(FinancialMetrics.extracted_at.desc())
    )

    result = await db.execute(stmt)
    metrics = result.scalars().first()

    # 3. Safe defaults
    if not metrics:
        metrics = FinancialMetrics(
            revenue=0,
            customers=0,
            cash=0,
            ebitda=0,
            gross_margin=0,
            operating_margin=0,
        )

    revenue = metrics.revenue or 0
    ebitda = metrics.ebitda or 0
    customers = metrics.customers or 0
    cash = metrics.cash or 0
    gross_margin = metrics.gross_margin or 0
    operating_margin = metrics.operating_margin or 0

    # 4. Response
    return {
        "report_id": report_id,
        "generated_at": report.created_at,

        "growth_metrics": {
            "revenue": revenue,
            "revenue_formatted": format_currency(revenue),
            "customers": customers,
            "revenue_per_customer": (revenue / customers) if customers else 0,
            "cagr_target_2030": 50.0,
        },

        "profitability": {
            "ebitda": ebitda,
            "ebitda_formatted": format_currency(ebitda),
            "gross_margin_percent": gross_margin,
            "operating_margin_percent": operating_margin,
            "ebitda_margin_percent": (ebitda / revenue * 100) if revenue else 0,
        },

        "liquidity": {
            "cash": cash,
            "cash_formatted": format_currency(cash),
            "cash_to_revenue_percent": (cash / revenue * 100) if revenue else 0,
        },

        # still valid from Report (AI layer)
        "key_findings": report.key_findings or [],
        "ai_commentary": report.ai_commentary or "",
    }

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
        return calc_change(curr, prev)

    return {
        "revenue": {
            "value": format_currency(latest.revenue),
            "change": round(change(
                latest.revenue,
                previous.revenue if previous else None
            ), 1),
            "trend": get_trend(change(
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
            "trend": get_trend(change(
                latest.customers,
                previous.customers if previous else None
            )),
        },
        "cash": {
            "value": format_currency(latest.cash),
            "change": round(change(
                latest.cash,
                previous.cash if previous else None
            ), 1),
            "trend": get_trend(change(
                latest.cash,
                previous.cash if previous else None
            )),
        },
        "ebitda": {
            "value": format_currency(latest.ebitda),
            "change": round(change(
                latest.ebitda,
                previous.ebitda if previous else None
            ), 1),
            "trend": get_trend(change(
                latest.ebitda,
                previous.ebitda if previous else None
            )),
        },
    }