"""Financial metrics endpoints."""
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.models.report import Report
from app.services.metrics_service import MetricsService
from app.schemas import DashboardPeriodOption, DashboardSummaryResponse, KPIMetric, RevenueTrendPoint

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

# A document the extractor found none of the four baseline figures in
# (e.g. a non-financial filing -- an AGM notice, a Memorandum & Articles of
# Association -- run through the same pipeline as a real filing, which the
# investor-relations import feature makes possible) must never be selected
# as "the latest" for dashboard purposes: it would silently blank out a
# real prior filing's data with an all-N/A row. Applied to both queries
# below that pick "the most recent N FinancialMetrics rows".
_HAS_CORE_METRICS = or_(
    FinancialMetrics.revenue.isnot(None),
    FinancialMetrics.customers.isnot(None),
    FinancialMetrics.cash.isnot(None),
    FinancialMetrics.ebitda.isnot(None),
)

# Only an `auto_accept`-tier extraction (see app/services/
# extraction_confidence.py) may drive the executive dashboard's headline
# KPIs -- a `needs_review` (85-94%) document is real and persisted, but
# must not silently become "the" board-facing number just because it
# cleared the (separate, lower) *reject* bar. `NULL` stays permissive so
# rows extracted before this feature existed (the original half-year
# filing) keep working exactly as they did before it existed. A row a
# human has explicitly reviewed and approved (POST
# /api/documents/{id}/approve, see documents.py) also qualifies --
# `human_approved_at` is a separate column from `extraction_confidence`,
# so this never rewrites the algorithmic score itself, only adds a second,
# independent way to earn dashboard eligibility.
_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD = or_(
    FinancialMetrics.extraction_confidence >= 95,
    FinancialMetrics.extraction_confidence.is_(None),
    FinancialMetrics.human_approved_at.isnot(None),
)

_EMPTY_RATIO = KPIMetric(value="N/A", change=0, trend="neutral", history=[])

_MONTH_LOOKUP = {
    name: index
    for index, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
    )
}


def _cadence_months(row: FinancialMetrics) -> Optional[int]:
    """
    Reporting cadence in months, derived from `reporting_period_start`/
    `reporting_period_end` (e.g. "Jul 2025"/"Dec 2025" -> 6, "Jul 2024"/
    "Jun 2025" -> 12). `None` when either label is missing or unparseable
    -- used by `get_revenue_trend` to keep documents of different cadences
    (e.g. a half-year filing and a full-year filing) from being silently
    blended into one trend line as if they were regular, comparable
    periods (see that endpoint's docstring for the real incident this
    prevents).
    """
    def _parse(label: Optional[str]) -> Optional[tuple[int, int]]:
        if not label:
            return None
        parts = label.split()
        if len(parts) != 2 or parts[0] not in _MONTH_LOOKUP or not parts[1].isdigit():
            return None
        return int(parts[1]), _MONTH_LOOKUP[parts[0]]

    start = _parse(row.reporting_period_start)
    end = _parse(row.reporting_period_end)
    if start is None or end is None:
        return None
    start_year, start_month = start
    end_year, end_month = end
    return (end_year - start_year) * 12 + (end_month - start_month) + 1


def _range_or_bare(start: Optional[str], end: Optional[str], bare: Optional[str]) -> Optional[str]:
    """
    Prefer a real calendar-month range (e.g. "Jul 2025 - Dec 2025") over
    the bare "HY2026" label wherever both start and end months were
    extracted -- "HY" alone doesn't say which calendar months a half-year
    covers (Senus's fiscal year runs Jul-Jun), so the range is strictly
    more informative when it's available. Shared by get_dashboard_metrics
    (current_period/prior_period) and _combined_period_label below.
    """
    return f"{start} – {end}" if start and end else bare


def _combined_period_label(bare: Optional[str], start: Optional[str], end: Optional[str], extracted_at) -> str:
    """
    Bare period + its calendar range together, e.g.
    "HY2026 (Jul 2025 – Dec 2025)" -- used by /dashboard/periods to label
    the period-selector dropdown's options, where showing both pieces at
    once (not preferring one over the other, unlike _range_or_bare) is
    what actually distinguishes two periods to someone scanning a list.
    Falls back to whichever piece is available, then to the extraction
    month/year when neither the bare label nor the range was extracted.
    """
    range_label = _range_or_bare(start, end, None)
    if bare and range_label:
        return f"{bare} ({range_label})"
    return bare or range_label or extracted_at.strftime("%b %Y")


async def _ai_reporting_periods_by_document(
    db: AsyncSession, document_ids: List[int]
) -> dict[int, str]:
    """
    Maps document_id -> AI-extracted reporting_period (e.g. "H1 2025") from
    Report.summary, for whichever of the given documents have it set. Used
    only as a fallback when FinancialMetrics.reporting_period (extracted
    deterministically -- see FinancialMetricsExtractor) wasn't found, since
    the AI/Gemini narrative path that populates Report.summary is skipped
    whenever the deterministic baseline extraction is already complete (see
    report_service._baseline_is_complete) and so is usually empty in
    practice. A single batched query rather than one per row --
    REVENUE_TREND_WINDOW rows would otherwise mean up to 24 round-trips.
    """
    if not document_ids:
        return {}
    stmt = select(Report.document_id, Report.summary).where(
        Report.document_id.in_(document_ids)
    )
    result = await db.execute(stmt)
    periods: dict[int, str] = {}
    for document_id, summary in result.all():
        period = (summary or {}).get("reporting_period")
        if period:
            periods[document_id] = period
    return periods


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

    # Same cadence-safety principle as get_revenue_trend below, applied
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

    previous = rows[1] if len(rows) > 1 else None

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
        # A None current value must render "N/A", not the formatter's own
        # None-default (format_currency renders "€0" for None, which would
        # misrepresent "not extracted" as a real zero -- the exact bug this
        # was hit by once already, see docs/roadmap.md).
        if curr_val is None:
            return KPIMetric(value="N/A", change=0, trend="neutral", history=history(field))
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
        current_period=current_period,
        prior_period=prior_period,
        data_extracted_at=latest.extracted_at,
        document_id=latest.document_id,
    )


@router.get("/dashboard/revenue-trend", response_model=List[RevenueTrendPoint])
async def get_revenue_trend(
    document_id: Optional[int] = Query(
        None,
        description="Anchor the trend on a specific document's reporting period instead of the "
        "true latest -- see GET /dashboard/periods for the available options.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Revenue by period (oldest -> newest) for the revenue trend chart, from the
    last REVENUE_TREND_WINDOW FinancialMetrics rows. `revenue` is null (not 0)
    for a document that didn't report it -- same missing-vs-zero convention as
    the sparkline history on /dashboard/summary.

    `document_id` anchors the trend the same way it anchors
    /dashboard/summary -- see that endpoint's docstring.
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
    rows = result.scalars().all()

    if document_id is None:
        anchor = rows[0] if rows else None
    else:
        anchor = next((r for r in rows if r.document_id == document_id), None)
        if anchor is None:
            raise HTTPException(
                status_code=404,
                detail="Requested period is not available on the dashboard.",
            )

    # Documents of different reporting cadence (e.g. this project's
    # half-year filing alongside a full-year "Information Document") must
    # never be blended into one trend line as if they were regular,
    # comparable periods -- confirmed against the real data: an annual
    # total (~€837K) plotted next to a half-year total (~€355K) as
    # sequential same-length points reads as a ~58% revenue collapse and
    # produces an actively misleading forecast (see `forecast.ts`'s
    # `projectSeries`, which has no notion of how much calendar time each
    # point covers). A row is excluded only when a *confirmed* mismatch
    # exists (both its own cadence and the anchor row's are known and
    # differ) -- most filings (including every existing test fixture)
    # don't set `reporting_period_start`/`_end` at all, and an unknown
    # cadence must not be treated as evidence of a mismatch, only a real,
    # positively-detected one.
    if anchor is not None:
        anchor_cadence = _cadence_months(anchor)
        if anchor_cadence is not None:
            rows = [
                r for r in rows
                if (row_cadence := _cadence_months(r)) is None or row_cadence == anchor_cadence
            ]
        # Same "as of that period" truncation as /dashboard/summary -- an
        # older selected period must not pull in a document extracted
        # after it.
        rows = [r for r in rows if r.extracted_at <= anchor.extracted_at]

    rows = rows[:REVENUE_TREND_WINDOW]

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
                    )
                ] + points

    return points
