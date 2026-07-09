"""
GET /metrics/dashboard/cost-waterfall and GET /metrics/dashboard/revenue-trend
-- the two chart-data endpoints on the executive dashboard.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.models.financial_metrics import FinancialMetrics
from app.schemas import CostWaterfallResponse, RevenueTrendPoint
from app.services.metrics_service import MetricsService

from ._shared import (
    _HAS_CORE_METRICS,
    _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD,
    REVENUE_TREND_WINDOW,
    _ai_reporting_periods_by_document,
    _cadence_months,
)

router = APIRouter()


@router.get("/dashboard/cost-waterfall", response_model=CostWaterfallResponse)
async def get_cost_waterfall(
    document_id: Optional[int] = Query(
        None,
        description="Anchor on a specific document's reporting period instead of the true latest -- "
        "same convention as GET /dashboard/summary.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Revenue -> Cost of Sales -> Gross Profit -> Administrative Expenses ->
    Operating Result (EBIT) -> D&A -> EBITDA, for the dashboard's cost
    waterfall chart (see docs/dashboard-review.md). Only some filing types
    disclose a full cost breakdown (BalanceSheetMetrics) -- `available` is
    False, with every figure None, whenever any required value is missing
    for the anchored period, rather than a waterfall with a fabricated gap.
    """
    stmt = (
        select(FinancialMetrics)
        .where(_HAS_CORE_METRICS, _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD)
        .order_by(FinancialMetrics.extracted_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        if document_id is not None:
            raise HTTPException(
                status_code=404,
                detail="Requested period is not available on the dashboard.",
            )
        return CostWaterfallResponse(available=False)

    if document_id is None:
        anchor = rows[0]
    else:
        anchor = next((r for r in rows if r.document_id == document_id), None)
        if anchor is None:
            raise HTTPException(
                status_code=404,
                detail="Requested period is not available on the dashboard.",
            )

    bs_stmt = select(BalanceSheetMetrics).where(BalanceSheetMetrics.document_id == anchor.document_id)
    bs_result = await db.execute(bs_stmt)
    bs = bs_result.scalars().first()

    revenue = anchor.revenue
    ebitda = anchor.ebitda
    cost_of_sales = bs.cost_of_sales if bs else None
    administrative_expenses = bs.administrative_expenses if bs else None
    operating_result = bs.operating_result if bs else None

    required = (revenue, cost_of_sales, administrative_expenses, operating_result, ebitda)
    if any(value is None for value in required):
        return CostWaterfallResponse(available=False, document_id=anchor.document_id)

    return CostWaterfallResponse(
        available=True,
        revenue=revenue,
        cost_of_sales=cost_of_sales,
        gross_profit=revenue - cost_of_sales,
        administrative_expenses=administrative_expenses,
        operating_result=operating_result,
        depreciation_amortization=ebitda - operating_result,
        ebitda=ebitda,
        document_id=anchor.document_id,
    )


@router.get("/dashboard/revenue-trend", response_model=List[RevenueTrendPoint])
async def get_revenue_trend(db: AsyncSession = Depends(get_db)):
    """
    Revenue by period (oldest -> newest) for the revenue trend chart, from the
    last REVENUE_TREND_WINDOW FinancialMetrics rows. `revenue` is null (not 0)
    for a document that didn't report it -- same missing-vs-zero convention as
    the sparkline history on /dashboard/summary.

    Unlike /dashboard/summary, this endpoint always returns *every* eligible
    document -- it deliberately does not anchor/truncate on a selected
    `document_id` the way the KPI cards do. The chart's job is "where does
    this period sit in the company's history", which needs the whole
    history regardless of which period is selected; the frontend does its
    own highlighting of the selected point using each point's `document_id`
    (added below) rather than the backend filtering rows out. See
    `docs/roadmap.md`'s "all-reports trend chart" entry for the real user
    complaint this replaced ("picking an older report shows a near-empty
    chart instead of the actual history").

    Each point also carries `cadence_months` (see `_cadence_months`) so the
    frontend can split half-year and full-year points into two separate
    lines -- they were previously excluded from each other outright (the
    real incident that guarded against blending a 12-month total and a
    6-month total on one line as if sequential, still fully honored, just
    enforced client-side now instead of by dropping rows server-side).
    """
    # Unlike /dashboard/summary above, this endpoint plots every document's
    # data independently per field (a document missing revenue specifically
    # still contributes a real point with a null revenue value) -- so
    # `_HAS_CORE_METRICS` is deliberately NOT applied here. Excluding a
    # document based on a cross-field "no signal at all" heuristic would
    # contradict the per-field missing-vs-zero convention this endpoint is
    # built on (see `optional_float` below). The exec-view confidence
    # boundary *is* applied, though -- this chart is still an executive
    # dashboard surface, same as /dashboard/summary.
    stmt = (
        select(FinancialMetrics)
        .where(_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD)
        .order_by(FinancialMetrics.extracted_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()[:REVENUE_TREND_WINDOW]

    ai_periods = await _ai_reporting_periods_by_document(db, [r.document_id for r in rows])

    def period_label(r: FinancialMetrics) -> str:
        # Prefer the calendar month/year (e.g. "Dec 2025") over the bare
        # "HY2026" label -- stakeholders found "HY" ambiguous (Senus's
        # fiscal year runs Jul-Jun, so "HY2026" doesn't end in June like a
        # reader might assume) and asked for a real month on the axis.
        # Falls back to the "HY" label, then the AI-extracted period, then
        # extracted_at (when we *processed* the upload, least accurate --
        # only used if nothing else is available).
        return (
            r.reporting_period_end
            or r.reporting_period
            or ai_periods.get(r.document_id)
            or r.extracted_at.strftime("%b %Y")
        )

    def optional_float(value) -> Optional[float]:
        return float(value) if value is not None else None

    points = [
        RevenueTrendPoint(
            period=period_label(r),
            revenue=optional_float(r.revenue),
            ebitda=optional_float(r.ebitda),
            cash=optional_float(r.cash),
            document_id=r.document_id,
            cadence_months=_cadence_months(r),
        )
        for r in reversed(rows)
    ]

    # With only one uploaded document (the realistic case today), there's no
    # second row to plot a real trend against -- but the filing embeds its
    # own prior-period comparative (`revenue_prior`), the same value the KPI
    # card's `history`/change% already uses (see get_dashboard_metrics
    # above). Prepending it here keeps the *chart* honest with the *card*:
    # without this, the card shows "+4.1% vs prior period" while the chart
    # right below it renders a single flat point, which reads as the delta
    # being fabricated when it isn't.
    if len(rows) < 2 and rows:
        latest = rows[0]
        if latest.revenue_prior is not None:
            prior_label = (
                latest.reporting_period_end_prior
                or latest.reporting_period_prior
                or MetricsService.derive_prior_period(period_label(latest))
            )
            if prior_label:
                points = [
                    RevenueTrendPoint(
                        period=prior_label,
                        revenue=float(latest.revenue_prior),
                        ebitda=optional_float(latest.ebitda_prior),
                        cash=optional_float(latest.cash_prior),
                        # No real document backs this point (it's derived
                        # from `latest`'s own embedded prior-period column,
                        # not a separate upload) -- `document_id=None` so
                        # the frontend's "is this the selected point"
                        # highlight never matches it, and so it's never
                        # mistaken for the real `latest` point it sits next
                        # to (which keeps its own real document_id below).
                        document_id=None,
                        cadence_months=_cadence_months(latest),
                    )
                ] + points

    return points
