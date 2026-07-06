"""Financial metrics endpoints."""
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.services.metrics_service import MetricsService
from app.schemas import DashboardSummaryResponse, KPIMetric, RevenueTrendPoint

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Metrics are always written internally by report generation
# (see ReportService._save_metrics) -- this router only reads them back
# for the dashboard. There is no client-facing metrics CRUD.

# Number of most-recent FinancialMetrics rows (one per uploaded document)
# to expose as sparkline history. Not calendar-aware -- see
# backend/docs/metrics-expansion-plan.md section 5 for the known gap
# around "latest two uploads" vs. true calendar-period comparisons.
HISTORY_WINDOW = 8

# Same caveat as HISTORY_WINDOW, but for the revenue trend chart -- filings
# may not be monthly (e.g. half-year results), so "period" is a display
# label derived from extracted_at, not a guaranteed-regular time axis.
REVENUE_TREND_WINDOW = 24

_EMPTY_RATIO = KPIMetric(value="N/A", change=0, trend="neutral", history=[])


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """
    Dashboard KPIs from FinancialMetrics table (latest + previous),
    plus up to HISTORY_WINDOW historical points per KPI for sparklines,
    plus Cash & Liquidity / Solvency & Leverage / Returns / Profitability
    ratios computed from BalanceSheetMetrics (see metrics-expansion-plan.md).
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
            ebitda_margin=_EMPTY_RATIO, cash_runway=_EMPTY_RATIO,
            interest_cover=_EMPTY_RATIO, roce=_EMPTY_RATIO, bookings=_EMPTY_RATIO,
        )

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None

    def prior_fallback(field: str) -> Optional[float]:
        # When there's no second DB row to diff against (today: only one
        # filing has ever been uploaded), fall back to the latest row's own
        # embedded prior-period comparative (e.g. `revenue_prior`, extracted
        # from the same filing's comparison column) so change/trend reflect
        # real YoY movement instead of always reading 0%/neutral.
        # getattr(..., default=None) is safe here even for fields with no
        # `_prior` column at all (e.g. "customers").
        if previous is not None:
            return getattr(previous, field)
        return getattr(latest, f"{field}_prior", None)

    def history(field: str) -> List[Optional[float]]:
        # Oldest -> newest. None means the document didn't report this field --
        # never coerce to 0.0 (see backend/docs/metrics-expansion-plan.md's
        # "missing-vs-zero" convention; this table already had that bug fixed once).
        values = [
            (float(v) if (v := getattr(r, field)) is not None else None)
            for r in reversed(rows)
        ]
        if len(rows) < 2:
            prior = getattr(latest, f"{field}_prior", None)
            if prior is not None:
                values = [float(prior)] + values
        return values

    def build(field: str, formatter: Callable[[Optional[float]], str]) -> KPIMetric:
        curr_val = getattr(latest, field)
        prev_val = prior_fallback(field)
        pct_change = round(MetricsService.calculate_change(curr_val, prev_val), 1)
        return KPIMetric(
            value=formatter(curr_val),
            change=pct_change,
            trend=MetricsService.get_trend(pct_change),
            history=history(field),
        )

    # --- Cash & Liquidity / Solvency & Leverage / Returns / Profitability ---
    # These come from BalanceSheetMetrics (a separate table -- see
    # backend/docs/metrics-expansion-plan.md), matched to the same document
    # as the latest FinancialMetrics row.
    bs_stmt = select(BalanceSheetMetrics).where(
        BalanceSheetMetrics.document_id == latest.document_id
    )
    bs_result = await db.execute(bs_stmt)
    bs = bs_result.scalars().first()

    ebitda = latest.ebitda
    ebitda_prior = prior_fallback("ebitda")
    revenue = latest.revenue
    revenue_prior = prior_fallback("revenue")
    cash = latest.cash
    cash_prior = prior_fallback("cash")

    net_cash_used = bs.net_cash_used_operating if bs else None
    net_cash_used_prior = bs.net_cash_used_operating_prior if bs else None
    interest_expense = bs.interest_expense if bs else None
    interest_expense_prior = bs.interest_expense_prior if bs else None
    operating_result = bs.operating_result if bs else None
    operating_result_prior = bs.operating_result_prior if bs else None
    capital_employed = bs.capital_employed if bs else None
    capital_employed_prior = bs.capital_employed_prior if bs else None

    def ratio_kpi(
        current: Optional[float],
        prior: Optional[float],
        formatter: Callable[[float], str],
    ) -> KPIMetric:
        if current is None:
            return KPIMetric(value="N/A", change=0, trend="neutral", history=[])
        pct_change = round(MetricsService.calculate_change(current, prior), 1) if prior is not None else 0
        trend = MetricsService.get_trend(pct_change) if prior is not None else "neutral"
        history_points = [v for v in (prior, current) if v is not None]
        return KPIMetric(
            value=formatter(current),
            change=pct_change,
            trend=trend,
            history=history_points,
        )

    ebitda_margin_current = MetricsService.ebitda_margin(ebitda, revenue)
    ebitda_margin_prior_val = MetricsService.ebitda_margin(ebitda_prior, revenue_prior)

    def cash_runway_kpi() -> KPIMetric:
        current = MetricsService.cash_runway_months(cash, net_cash_used)
        prior = MetricsService.cash_runway_months(cash_prior, net_cash_used_prior)

        if current is None:
            # "runway" isn't a meaningful concept when operations aren't
            # burning cash -- distinguish that from genuinely missing data.
            is_cash_flow_positive = net_cash_used is not None and net_cash_used <= 0
            return KPIMetric(
                value="Cash flow +" if is_cash_flow_positive else "N/A",
                change=0,
                trend="neutral",
                history=[],
            )

        pct_change = round(MetricsService.calculate_change(current, prior), 1) if prior is not None else 0
        return KPIMetric(
            value=f"{current:.1f} mo",
            change=pct_change,
            trend=MetricsService.get_trend(pct_change) if prior is not None else "neutral",
            history=[v for v in (prior, current) if v is not None],
        )

    interest_cover_current = MetricsService.interest_cover(ebitda, interest_expense)
    interest_cover_prior_val = MetricsService.interest_cover(ebitda_prior, interest_expense_prior)

    roce_current = MetricsService.roce(operating_result, capital_employed)
    roce_prior_val = MetricsService.roce(operating_result_prior, capital_employed_prior)

    def bookings_kpi() -> KPIMetric:
        # Narrative-extracted, no prior-period comparative exists for this
        # field (same as `customers`) -- change/trend are always 0/neutral,
        # never a fabricated delta. `build()` isn't reused here because its
        # formatter would render a missing value as "€0" (format_currency's
        # None-default), which would misrepresent "not extracted" as a real
        # zero-value bookings figure.
        value = latest.bookings_value
        if value is None:
            return KPIMetric(value="N/A", change=0, trend="neutral", history=[])
        return KPIMetric(
            value=MetricsService.format_currency(value),
            change=0,
            trend="neutral",
            history=[value],
        )

    return DashboardSummaryResponse(
        revenue=build("revenue", MetricsService.format_currency),
        customers=build("customers", lambda v: f"{int(v or 0):,}"),
        cash=build("cash", MetricsService.format_currency),
        ebitda=build("ebitda", MetricsService.format_currency),
        ebitda_margin=ratio_kpi(ebitda_margin_current, ebitda_margin_prior_val, lambda v: f"{v:.1f}%"),
        cash_runway=cash_runway_kpi(),
        interest_cover=ratio_kpi(interest_cover_current, interest_cover_prior_val, lambda v: f"{v:.1f}x"),
        roce=ratio_kpi(roce_current, roce_prior_val, lambda v: f"{v:.1f}%"),
        bookings=bookings_kpi(),
    )


@router.get("/dashboard/revenue-trend", response_model=List[RevenueTrendPoint])
async def get_revenue_trend(db: AsyncSession = Depends(get_db)):
    """
    Revenue by period (oldest -> newest) for the revenue trend chart, from the
    last REVENUE_TREND_WINDOW FinancialMetrics rows. `revenue` is null (not 0)
    for a document that didn't report it -- same missing-vs-zero convention as
    the sparkline history on /dashboard/summary.
    """
    stmt = (
        select(FinancialMetrics)
        .order_by(FinancialMetrics.extracted_at.desc())
        .limit(REVENUE_TREND_WINDOW)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        RevenueTrendPoint(
            period=r.extracted_at.strftime("%b %Y"),
            revenue=(float(r.revenue) if r.revenue is not None else None),
        )
        for r in reversed(rows)
    ]
