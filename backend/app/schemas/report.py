"""
Pydantic schemas for report endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ReportCreate(BaseModel):
    """Schema for creating a report."""
    document_id: int = Field(..., description="ID of document to analyze")


class ReportResponse(BaseModel):
    """Schema for report API responses."""
    
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    ai_commentary: str = Field(..., description="AI-generated executive summary")
    summary: List[str] = Field(..., description="Bullet-point key findings")
    created_at: datetime
    updated_at: datetime