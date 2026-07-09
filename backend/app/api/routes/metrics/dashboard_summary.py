"""
GET /metrics/dashboard/periods and GET /metrics/dashboard/summary -- the
period selector's option list and the executive dashboard's headline KPIs
(latest + previous + sparkline history + Cash & Liquidity / Solvency &
Leverage / Returns / Profitability ratios).
"""
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.models.financial_metrics import FinancialMetrics
from app.schemas import DashboardPeriodOption, DashboardSummaryResponse, KPIMetric
from app.services.metrics_service import MetricsService

from ._shared import (
    _EMPTY_RATIO,
    _HAS_CORE_METRICS,
    _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD,
    _MISSING_VALUE_MESSAGES,
    HISTORY_WINDOW,
    _ai_reporting_periods_by_document,
    _cadence_months,
    _combined_period_label,
    _range_or_bare,
    _select_previous,
)

router = APIRouter()


@router.get("/dashboard/periods", response_model=List[DashboardPeriodOption])
async def get_dashboard_periods(db: AsyncSession = Depends(get_db)):
    """
    Available reporting periods for the dashboard's period selector --
    exactly the set of rows eligible to ever become "latest" on
    /dashboard/summary (same _HAS_CORE_METRICS/_IS_CONFIDENT_ENOUGH_FOR_
    DASHBOARD filters), newest first. Each label combines the bare period
    (e.g. "HY2026") with its real calendar range when known, e.g.
    "HY2026 (Jul 2025 – Dec 2025)".
    """
    stmt = (
        select(FinancialMetrics)
        .where(_HAS_CORE_METRICS, _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD)
        .order_by(FinancialMetrics.extracted_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    ai_periods = await _ai_reporting_periods_by_document(db, [r.document_id for r in rows])

    return [
        DashboardPeriodOption(
            document_id=row.document_id,
            label=_combined_period_label(
                row.reporting_period or ai_periods.get(row.document_id),
                row.reporting_period_start,
                row.reporting_period_end,
                row.extracted_at,
            ),
        )
        for row in rows
    ]


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_metrics(
    document_id: Optional[int] = Query(
        None,
        description="Anchor the dashboard on a specific document's reporting period instead of "
        "the true latest -- see GET /dashboard/periods for the available options.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard KPIs from FinancialMetrics table (latest + previous),
    plus up to HISTORY_WINDOW historical points per KPI for sparklines,
    plus Cash & Liquidity / Solvency & Leverage / Returns / Profitability
    ratios computed from BalanceSheetMetrics (see metrics-expansion-plan.md).

    `document_id` lets the period selector anchor the dashboard on an
    older period instead of the true latest -- "latest"/"previous"/history
    then mean "as of that period", i.e. that period plus its own
    same-cadence history, never anything extracted after it.
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
            # An explicitly requested period doesn't exist among the (zero)
            # eligible rows -- a 404, not a silent fall-through to the
            # generic empty-dashboard state below.
            raise HTTPException(
                status_code=404,
                detail="Requested period is not available on the dashboard.",
            )
        # No data at all -- either nothing has ever been uploaded, or every
        # uploaded document's extraction found nothing usable (a non-
        # financial document, filtered out by _HAS_CORE_METRICS above). "N/A"
        # here, not a fabricated "€0"/"0" -- same reasoning as `build()` below.
        return DashboardSummaryResponse(
            revenue=_EMPTY_RATIO, customers=_EMPTY_RATIO, cash=_EMPTY_RATIO, ebitda=_EMPTY_RATIO,
            ebitda_margin=_EMPTY_RATIO, cash_runway=_EMPTY_RATIO,
            interest_cover=_EMPTY_RATIO, roce=_EMPTY_RATIO, bookings=_EMPTY_RATIO,
            gross_margin=_EMPTY_RATIO, operating_margin=_EMPTY_RATIO,
            current_period=None, prior_period=None, document_id=None,
        )

    if document_id is None:
        anchor = rows[0]
    else:
        anchor = next((r for r in rows if r.document_id == document_id), None)
        if anchor is None:
            raise HTTPException(
                status_code=404,
                detail="Requested period is not available on the dashboard.",
            )

    # Same cadence-safety principle as get_revenue_trend (charts.py), applied
    # here too -- a real incident found live in production, not
    # hypothetical: comparing a 12-month total against a 6-month total as
    # if they were sequential periods produced a fabricated "+135.9%"
    # revenue change (837K vs. the half-year filing's 355K) instead of the
    # real, honest FY2025-vs-FY2024 comparison (837K vs. 688K, +21.6%,
    # from the Information Document's own embedded revenue_prior). A row
    # is excluded from `previous`/`history` only on a *confirmed* cadence
    # mismatch (both known and different) -- an unknown cadence is never
    # treated as evidence of a mismatch.
    anchor_cadence = _cadence_months(anchor)
    if anchor_cadence is not None:
        rows = [
            r for r in rows
            if (row_cadence := _cadence_months(r)) is None or row_cadence == anchor_cadence
        ]

    # Selecting an older period should show the dashboard as it looked "as
    # of" that period -- that period plus its own same-cadence history --
    # not leak in data from a document extracted after it.
    rows = [r for r in rows if r.extracted_at <= anchor.extracted_at][:HISTORY_WINDOW]

    latest = rows[0]  # == anchor, by construction of the filters above

    previous = _select_previous(anchor, rows[1:])

    # Prefer the deterministic extractor's own reporting_period/_prior
    # (e.g. "HY2026"/"HY25", extracted directly from the filing's text) --
    # falls back to the AI-extracted Report.summary field (usually empty in
    # practice, see the helper's docstring), then to a best-effort derived
    # prior label when only a current period is known.
    ai_periods = await _ai_reporting_periods_by_document(db, [latest.document_id])
    current_bare = latest.reporting_period or ai_periods.get(latest.document_id)
    prior_bare = latest.reporting_period_prior or MetricsService.derive_prior_period(current_bare)

    current_period = _range_or_bare(latest.reporting_period_start, latest.reporting_period_end, current_bare)
    prior_period = _range_or_bare(latest.reporting_period_start_prior, latest.reporting_period_end_prior, prior_bare)

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
        # A None current value must render a field-specific missing-value
        # message, not the formatter's own None-default (format_currency
        # renders "€0" for None, which would misrepresent "not extracted" as
        # a real zero -- the exact bug this was hit by once already, see
        # docs/roadmap.md).
        if curr_val is None:
            return KPIMetric(
                value=_MISSING_VALUE_MESSAGES.get(field, "N/A"), change=0, trend="neutral",
                history=history(field), available=False,
            )
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
        field: str,
        current: Optional[float],
        prior: Optional[float],
        formatter: Callable[[float], str],
    ) -> KPIMetric:
        if current is None:
            return KPIMetric(
                value=_MISSING_VALUE_MESSAGES.get(field, "N/A"), change=0, trend="neutral",
                history=[], available=False,
            )
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
                value="Cash flow +" if is_cash_flow_positive else _MISSING_VALUE_MESSAGES["cash_runway"],
                change=0,
                trend="neutral",
                history=[],
                # "Cash flow +" is a real, meaningful signal (operations
                # aren't burning cash, so "runway" isn't a relevant concept)
                # -- not missing data, so it should never trigger the
                # adaptive-cascade fallback the way a genuine gap does.
                available=is_cash_flow_positive,
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
            return KPIMetric(
                value=_MISSING_VALUE_MESSAGES["bookings"], change=0, trend="neutral",
                history=[], available=False,
            )
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
        ebitda_margin=ratio_kpi("ebitda_margin", ebitda_margin_current, ebitda_margin_prior_val, lambda v: f"{v:.1f}%"),
        cash_runway=cash_runway_kpi(),
        interest_cover=ratio_kpi("interest_cover", interest_cover_current, interest_cover_prior_val, lambda v: f"{v:.1f}x"),
        roce=ratio_kpi("roce", roce_current, roce_prior_val, lambda v: f"{v:.1f}%"),
        bookings=bookings_kpi(),
        gross_margin=build("gross_margin", lambda v: f"{v:.1f}%"),
        operating_margin=build("operating_margin", lambda v: f"{v:.1f}%"),
        current_period=current_period,
        prior_period=prior_period,
        data_extracted_at=latest.extracted_at,
        document_id=latest.document_id,
    )
