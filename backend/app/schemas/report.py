"""
Pydantic response schemas for the reports API.

`Report.summary` / `Report.ai_commentary` are populated by
`ReportService._generate` from a merge of the deterministic baseline
extractor and (optionally) Gemini AI enrichment -- these schemas pin
down the shape the frontend can rely on once that merge is normalized.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReportMetricsSummary(BaseModel):
    """Normalized financial metrics as they appear in `Report.summary['metrics']`."""

    revenue: Optional[float] = None
    customers: Optional[float] = None
    cash: Optional[float] = None
    ebitda: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None


class ReportSummary(BaseModel):
    """Shape of `Report.summary`."""

    company_name: Optional[str] = None
    reporting_period: Optional[str] = None
    metrics: ReportMetricsSummary = Field(default_factory=ReportMetricsSummary)
    key_findings: List[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """Response schema for report create/get/list/regenerate endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    ai_commentary: Optional[str] = None
    key_findings: Optional[List[str]] = None
    summary: Optional[ReportSummary] = None
    status: str
    generation_source: Optional[str] = None
    model_version: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class ReportDeleteResponse(BaseModel):
    deleted: bool


# ==================== Dashboard ====================
class DashboardDocument(BaseModel):
    id: int
    name: str


class ReportDashboardResponse(BaseModel):
    """Response schema for `GET /api/reports/{id}/dashboard`."""

    report_id: int
    document: DashboardDocument
    financial_metrics: ReportMetricsSummary
    key_findings: List[str]
    ai_commentary: Optional[str] = None
    generated_at: datetime
    model: Optional[str] = None
