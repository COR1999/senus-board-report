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


# ==================== AI Board Insights (persisted) ====================
# The frontend's own Gemini integration (`GEMINI_INSIGHTS_API_KEY`,
# app/api/insights/route.ts) generates these client-side; the backend only
# ever persists what the frontend already generated -- see
# `app/models/report_insights.py` for the full reasoning.
class StoredInsight(BaseModel):
    """Mirrors the frontend's own `Insight` shape (frontend/lib/insights.ts) exactly."""

    text: str
    type: str
    action: str = ""
    category: Optional[str] = None


class ReportInsightsUpsert(BaseModel):
    """Request body for PUT /api/reports/{report_id}/insights."""

    insights: List[StoredInsight]
    model_version: Optional[str] = None


class ReportInsightsResponse(BaseModel):
    """Response schema for GET/PUT /api/reports/{report_id}/insights."""

    model_config = ConfigDict(from_attributes=True)

    report_id: int
    insights: List[StoredInsight]
    model_version: Optional[str] = None
    generated_at: datetime


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
