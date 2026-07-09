"""
Constants and period/cadence helpers shared across every /metrics/dashboard
endpoint. Nothing here is FastAPI-specific -- these are the same building
blocks `dashboard_summary.py`, `charts.py`, and `historical_insight.py` all
extend into an actual route handler.
"""
import hashlib
import json
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.schemas import KPIMetric, RevenueTrendPoint

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
# independent way to earn dashboard eligibility. A row that's been
# `superseded_by_document_id` (see period_merge_service.py -- two documents
# independently reporting the exact same period, merged into a new one) is
# excluded unconditionally: the merged document is what should drive the
# dashboard for that period now, never the originals it was built from.
_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD = and_(
    or_(
        FinancialMetrics.extraction_confidence >= 95,
        FinancialMetrics.extraction_confidence.is_(None),
        FinancialMetrics.human_approved_at.isnot(None),
    ),
    FinancialMetrics.superseded_by_document_id.is_(None),
)

_EMPTY_RATIO = KPIMetric(value="No data yet", change=0, trend="neutral", history=[], available=False)

# Field-specific missing-value copy, shown instead of a bare "N/A" -- a real
# user-facing readability request: "N/A" doesn't say *what's* missing, and a
# board reader shouldn't have to guess whether a field is unreported, not
# calculable, or something went wrong. Only covers the fields `build()`/
# `ratio_kpi()`/`bookings_kpi()` (dashboard_summary.py) can actually report
# missing -- not used for `_EMPTY_RATIO` above, which is a different case
# entirely (no eligible document exists at all, not "this one document
# skipped a field").
_MISSING_VALUE_MESSAGES = {
    "revenue": "Revenue not reported in this filing",
    "customers": "Customer count not reported in this filing",
    "cash": "Cash position not reported in this filing",
    "ebitda": "EBITDA not reported in this filing",
    "ebitda_margin": "EBITDA margin not available (EBITDA not reported)",
    "cash_runway": "Cash runway not available (insufficient data)",
    "interest_cover": "Interest cover not available (no interest expense reported)",
    "roce": "ROCE not available (insufficient balance sheet data)",
    "bookings": "No bookings reported in this filing",
    "gross_margin": "Gross margin not reported in this filing",
    "operating_margin": "Operating margin not reported in this filing",
}

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


def _covers_same_period(a: FinancialMetrics, b: FinancialMetrics) -> bool:
    """
    True when both rows report the exact same calendar period (e.g. both
    "Jul 2024 - Jun 2025") -- distinct from same *cadence* (both 12-month
    filings), which two DIFFERENT full years both satisfy. Only true when
    both rows have known start/end labels; an unknown period is never
    treated as a match (same permissive-by-default principle as
    `_cadence_months`'s callers).

    A real production bug, not hypothetical: ADF Farm Solutions (a genuine
    FY2025 filing, vision-extracted) and the Information Document (also
    FY2025, for the same underlying company under a prior name) both
    report the *same* period -- picking "the next most recent document" as
    ADF's `previous` grabbed the Information Document's own FY2025 figure
    instead of a real prior year, producing a fabricated "0% change"
    (836,991 diffed against itself) even though a real FY2024 comparative
    existed elsewhere. See `_select_previous` below.
    """
    return (
        a.reporting_period_start is not None
        and a.reporting_period_end is not None
        and a.reporting_period_start == b.reporting_period_start
        and a.reporting_period_end == b.reporting_period_end
    )


def _select_previous(anchor: FinancialMetrics, candidates: List[FinancialMetrics]) -> Optional[FinancialMetrics]:
    """
    The row to diff `anchor` against for change%/trend -- the most recent
    *genuinely different* period among `candidates` (already same-cadence-
    filtered and extracted-before-or-with `anchor`). Skips past any row
    covering the identical period as `anchor` (see `_covers_same_period`)
    rather than treating a same-period duplicate document as if it were a
    real prior year. `None` when no genuinely different period exists --
    `prior_fallback` (in dashboard_summary.py) then falls back to `anchor`'s
    own embedded `_prior` field rather than a wrong document-level comparison.
    """
    return next((r for r in candidates if not _covers_same_period(anchor, r)), None)


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


def _chart_data_fingerprint(points: List[RevenueTrendPoint]) -> str:
    """
    A stable hash of the exact revenue-trend data set (same points
    `GET /dashboard/revenue-trend` returns) -- lets the historical-insight
    endpoints detect whether the underlying all-reports data has changed
    since an insight was last generated, without storing/diffing the full
    point list itself. Field order is fixed explicitly (not relying on
    Pydantic's own key order) so the hash is stable across schema reorderings.
    """
    payload = [
        {
            "period": p.period,
            "revenue": p.revenue,
            "ebitda": p.ebitda,
            "cash": p.cash,
            "document_id": p.document_id,
            "cadence_months": p.cadence_months,
        }
        for p in points
    ]
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
