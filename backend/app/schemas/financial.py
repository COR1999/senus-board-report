"""
Pydantic schemas for financial data.
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


# ==================== Financial Metrics ====================
class FinancialMetricsBase(BaseModel):
    """Base financial metrics schema."""
    revenue: Optional[float] = Field(None, description="Annual revenue in thousands")
    customers: Optional[int] = Field(None, description="Number of customers")
    cash: Optional[float] = Field(None, description="Cash on hand in thousands")
    ebitda: Optional[float] = Field(None, description="EBITDA in thousands")
    gross_margin: Optional[float] = Field(None, description="Gross margin percentage (0-100)")
    operating_margin: Optional[float] = Field(None, description="Operating margin percentage (0-100)")


class FinancialMetricsCreate(FinancialMetricsBase):
    """Schema for creating financial metrics."""
    document_id: int


class FinancialMetricsResponse(FinancialMetricsBase):
    """Financial metrics response schema."""
    id: Optional[int] = None
    document_id: Optional[int] = None
    extracted_at: Optional[datetime] = None
    # See app/services/extraction_confidence.py. Both None for any row
    # extracted before this feature existed (the original half-year
    # filing) -- the frontend must treat that the same as "no concerns",
    # not as a broken/missing value.
    extraction_confidence: Optional[float] = Field(
        None, description="0-100 extraction confidence score, or null if not yet scored."
    )
    extraction_confidence_tier: Optional[str] = Field(
        None, description="'auto_accept' / 'needs_review' / 'rejected', or null if not yet scored."
    )
    extraction_confidence_reasons: Optional[List[str]] = Field(
        None, description="Human-readable point breakdown behind the score above -- see score_extraction()."
    )

    model_config = ConfigDict(from_attributes=True)


# ==================== Dashboard Summary ====================
class KPIMetric(BaseModel):
    """A single KPI card's data: current value, delta vs previous, and sparkline history."""
    value: str = Field(..., description="Pre-formatted display value, e.g. '€836K'")
    change: float = Field(..., description="Percent change vs previous period")
    trend: Literal["up", "down", "neutral"]
    history: List[Optional[float]] = Field(
        default_factory=list,
        description=(
            "Raw numeric values, oldest→newest, for sparkline rendering. "
            "A null entry means that document didn't report the field (missing, "
            "not zero) -- never coerce missing data to 0."
        ),
    )


class DashboardSummaryResponse(BaseModel):
    """Response for GET /metrics/dashboard/summary."""
    revenue: KPIMetric
    customers: KPIMetric
    cash: KPIMetric
    ebitda: KPIMetric
    # Cash & Liquidity / Solvency & Leverage / Returns / Profitability --
    # see backend/docs/metrics-expansion-plan.md. `history` for these is
    # at most [prior, current] (2 points) from the single filing's own
    # comparative column, not a multi-document time series like the four
    # KPIs above.
    ebitda_margin: KPIMetric
    cash_runway: KPIMetric
    interest_cover: KPIMetric
    roce: KPIMetric
    # Growth & Revenue -- narrative-extracted, no prior-period comparative
    # exists for this field (same as `customers`), so change/trend are
    # always 0/neutral rather than a real computed delta.
    bookings: KPIMetric
    # AI-extracted free-text reporting period for the latest document (e.g.
    # "H1 2025"), and a best-effort prior-period label derived from it (e.g.
    # "H1 2024") -- lets the frontend show real date context on KPI cards
    # instead of a generic, sometimes-inaccurate "vs last quarter"/"vs last
    # month". Both None when no report/summary exists yet for the latest
    # document (e.g. still generating) or its period couldn't be parsed --
    # never a guessed/fabricated label.
    current_period: Optional[str] = None
    prior_period: Optional[str] = None
    # When this data was actually extracted (the "latest" FinancialMetrics
    # row's own extracted_at) -- distinct from `current_period` (the
    # filing's *reporting* period, e.g. "FY2025"). Powers the dashboard's
    # global "Data as of ..." banner so a board reader always knows how
    # fresh the figures are, independent of which period they cover. None
    # only when there's no data at all yet.
    data_extracted_at: Optional[datetime] = None
    # The document backing "latest"/current_period above -- normally the
    # true most-recently-extracted document, but reflects whichever
    # document_id the period selector anchored this response on (see
    # GET /metrics/dashboard/periods and the `document_id` query param on
    # this endpoint). None only in the no-data-at-all empty state.
    document_id: Optional[int] = None


# ==================== Dashboard Periods ====================
class DashboardPeriodOption(BaseModel):
    """One entry in GET /metrics/dashboard/periods, for the period selector."""
    document_id: int
    label: str = Field(..., description="Combined bare period + calendar range, e.g. 'HY2026 (Jul 2025 – Dec 2025)'")


# ==================== Revenue Trend ====================
class RevenueTrendPoint(BaseModel):
    """One point on the revenue trend chart."""
    period: str = Field(..., description="Display label for the period, e.g. 'Dec 2025'")
    revenue: Optional[float] = Field(
        None,
        description="Revenue for this period. Null means the document didn't report it -- never 0.",
    )
    ebitda: Optional[float] = Field(
        None,
        description="EBITDA for this period. Null means the document didn't report it -- never 0.",
    )
    cash: Optional[float] = Field(
        None,
        description="Cash for this period. Null means the document didn't report it -- never 0.",
    )
    document_id: Optional[int] = Field(
        None,
        description="The document this point came from -- lets the frontend highlight whichever "
        "point matches the currently-selected period. Null only for the single synthetic "
        "prior-period point get_revenue_trend may prepend when just one document exists (that "
        "point is derived from the real document's own embedded prior-period column, not a "
        "separate upload).",
    )
    cadence_months: Optional[int] = Field(
        None,
        description="This point's reporting cadence in months (6 for half-year, 12 for full-year), "
        "when derivable -- lets the frontend split the chart into separate half-year/full-year "
        "lines instead of connecting incomparable period lengths on one line. Null when the "
        "cadence couldn't be determined (see _cadence_months) -- rendered as an isolated point, "
        "not guessed into either line.",
    )


# ==================== Historical trend insight ====================
# One AI-generated insight describing the trend across EVERY report on file
# (not one report's own snapshot) -- see app/models/historical_insight.py.
# The Gemini call itself stays entirely frontend-side (same architecture as
# every other AI Board Insight); these endpoints only ever persist what the
# frontend already generated.
class HistoricalInsightPayload(BaseModel):
    """Mirrors the frontend's own `Insight` shape (frontend/lib/insights.ts) exactly."""

    text: str
    type: str
    action: str = ""
    category: Optional[str] = None


class HistoricalInsightUpsert(BaseModel):
    """Request body for PUT /metrics/dashboard/historical-insight."""

    insight: HistoricalInsightPayload
    model_version: Optional[str] = None


class HistoricalInsightResponse(BaseModel):
    """Response schema for GET/PUT /metrics/dashboard/historical-insight."""

    model_config = ConfigDict(from_attributes=True)

    insight: HistoricalInsightPayload
    model_version: Optional[str] = None
    generated_at: datetime


# ==================== Document ====================
class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str
    file_size: Optional[int] = None


class DocumentCreate(DocumentBase):
    """Schema for creating documents."""
    pass


class DocumentResponse(DocumentBase):
    id: int
    file_path: Optional[str] = None
    status: str
    created_at: datetime
    # Populated by a separate batched query in list_documents() (see
    # app/services/extraction_confidence.py) -- not a real column on
    # Document itself, so `from_attributes` alone won't fill it; the route
    # sets it explicitly per row. None for a document with no
    # FinancialMetrics row yet, or one extracted before this feature
    # existed.
    extraction_confidence_tier: Optional[str] = None
    # Populated the same way as extraction_confidence_tier above -- set when
    # this document's data has been merged into a new combined document
    # covering the same reporting period (see period_merge_service.py).
    # `None` for the overwhelming majority of documents, which aren't
    # superseded by anything.
    superseded_by_document_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentWithText(DocumentResponse):
    extracted_text: Optional[str] = None
    extracted_at: Optional[datetime] = None
    financial_metrics: Optional[FinancialMetricsResponse] = None
    report_id: Optional[int] = Field(None, description="Associated report ID if available")


class ExternalFilingSummary(BaseModel):
    """A filing on Senus's investor relations API not yet imported here."""
    attachment_id: str
    file_name: str
    file_size: Optional[int] = None
    published_date: Optional[str] = None