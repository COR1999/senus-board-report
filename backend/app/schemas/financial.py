"""Pydantic schemas for financial data."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class FinancialMetricsBase(BaseModel):
    """Base financial metrics schema."""
    
    revenue: float = Field(..., gt=0, description="Revenue in EUR")
    customers: int = Field(..., gt=0, description="Number of customers")
    cash: float = Field(..., ge=0, description="Cash balance in EUR")
    ebitda: Optional[float] = Field(None, description="EBITDA in EUR")
    gross_margin: Optional[float] = Field(None, ge=0, le=100, description="Gross margin %")
    operating_margin: Optional[float] = Field(None, description="Operating margin %")


class FinancialMetricsCreate(FinancialMetricsBase):
    """Schema for creating metrics."""
    document_id: str


class FinancialMetricsResponse(FinancialMetricsBase):
    """Schema for metrics response."""
    
    id: str
    document_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str = Field(..., min_length=1, max_length=255)


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    
    id: str
    created_at: datetime
    extracted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentWithText(DocumentResponse):
    """Schema for document response with extracted text."""
    
    extracted_text: str
    status: str
    financial_metrics: Optional[FinancialMetricsResponse] = None


class ReportBase(BaseModel):
    """Base report schema."""
    ai_commentary: Optional[str] = None
    summary: Optional[str] = None


class ReportResponse(ReportBase):
    """Schema for report response."""
    
    id: str
    document_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True