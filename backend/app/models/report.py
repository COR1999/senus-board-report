"""
Report SQLAlchemy model using SQLAlchemy 2.0 style.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Report(Base):
    """
    Report model for storing AI-generated analysis.
    """
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    ai_commentary: Mapped[Optional[str]] = mapped_column(default=None)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)
    # raw_metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship
    document: Mapped["Document"] = relationship(back_populates="reports")