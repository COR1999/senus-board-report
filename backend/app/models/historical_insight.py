from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class HistoricalInsight(Base):
    """
    A single AI-generated insight describing the trend across EVERY report on
    file (not one report's own snapshot -- see `app/models/report_insights.py`
    for that), regenerated only when the underlying all-reports chart data
    actually changes. Genuinely singleton: this project is a single-user
    boardroom tool with one dashboard, so there is exactly one "the trend
    across all reports" to describe -- unlike `ReportInsights`, there's no
    natural foreign key to scope this by.

    `data_fingerprint` is a hash of the exact chart-data set (document_id,
    revenue, ebitda, cash, cadence_months per point) the stored `insight` was
    generated from -- `GET /metrics/dashboard/historical-insight` compares it
    against a freshly computed fingerprint and only returns the stored row
    when they match, mirroring the "regenerate only when the underlying data
    actually changed" principle already used for the per-report case.
    """
    __tablename__ = "historical_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # A single StoredInsight (text/type/action/category), not a list -- this
    # endpoint always describes the whole history in exactly one insight.
    insight: Mapped[dict] = mapped_column(JSONB, nullable=False)

    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
