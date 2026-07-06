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