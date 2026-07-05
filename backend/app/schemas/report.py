from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


# ====================== Base ======================
class ReportBase(BaseModel):
    ai_commentary: Optional[str] = Field(None, description="AI-generated executive summary / commentary")
    key_findings: Optional[List[str]] = Field(None, description="List of bullet-point key findings")
    summary: Optional[dict] = Field(None, description="Structured/raw metrics or additional summary data")


# ====================== Create ======================
class ReportCreate(BaseModel):
    """Trigger report generation"""
    document_id: int = Field(..., gt=0, description="ID of the document to generate a report for")


# ====================== Update ======================
class ReportUpdate(BaseModel):
    ai_commentary: Optional[str] = None
    key_findings: Optional[List[str]] = None
    summary: Optional[dict] = None


# ====================== Response ======================
class ReportResponse(ReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    status: str = "pending"
    generation_source: Optional[str] = None
    model_version: Optional[str] = None
    version: int = 1
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int
    page: int
    size: int


# ====================== With Document ======================
class DocumentInReport(BaseModel):
    """Lightweight document info for report responses"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    status: str


class ReportWithDocument(ReportResponse):
    document: Optional[DocumentInReport] = None


# Forward reference (optional)
ReportWithDocument.model_rebuild()