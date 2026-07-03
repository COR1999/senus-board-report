"""
Pydantic schemas for financial data.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
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


# ==================== Report ====================
class ReportBase(BaseModel):
    """Base report schema."""
    report_type: str = "financial_analysis"


class ReportCreate(ReportBase):
    """Schema for creating reports."""
    document_id: int
    include_metrics: bool = True
    include_commentary: bool = True


class ReportResponse(ReportBase):
    """Report response schema."""
    id: int
    document_id: int
    ai_commentary: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    raw_metrics: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ReportWithDocument(ReportResponse):
    """Report with associated document."""
    document: DocumentResponse


# ==================== Health Check ====================
class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    database: str
    gemini_api: str
    version: str