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

    model_config = ConfigDict(from_attributes=True)


class DocumentWithText(DocumentResponse):
    extracted_text: Optional[str] = None
    extracted_at: Optional[datetime] = None
    financial_metrics: Optional[FinancialMetricsResponse] = None
    report_id: Optional[int] = Field(None, description="Associated report ID if available")