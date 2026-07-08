from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.report import Report


class ReportInsights(Base):
    """
    Persisted AI Board Insights for a single report -- the frontend's own
    Gemini integration (`GEMINI_INSIGHTS_API_KEY`, `app/api/insights/route.ts`
    on the Next.js side, entirely separate quota from the backend's own
    `gemini_service.py`) generates these client-side; this table is only ever
    written to *after* a real (non-fallback) generation succeeds, via
    `PUT /api/reports/{report_id}/insights`.

    One row per report (`report_id` unique), not one row per document -- a
    regenerated report is a genuinely new analysis of possibly-different
    data, so it gets its own insights rather than inheriting the prior
    report's. Deleting a report cascades (matches `Report`'s own relationship
    to `Document`), since insights for a report that no longer exists are
    meaningless.
    """
    __tablename__ = "report_insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Each item: {text, type, action, category} -- mirrors the frontend's own
    # `Insight` shape exactly (see frontend/lib/insights.ts). Stored whole,
    # never queried into individual fields, same reasoning already used for
    # `FinancialMetrics.extraction_confidence_reasons`.
    insights: Mapped[List[dict]] = mapped_column(JSONB, nullable=False)

    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    report: Mapped["Report"] = relationship()
