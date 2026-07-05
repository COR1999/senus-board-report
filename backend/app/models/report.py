from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Content generated for the report.
    ai_commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_findings: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Processing and lifecycle metadata.
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    generation_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    version: Mapped[int] = mapped_column(default=1, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship back to the parent document.
    document: Mapped["Document"] = relationship(back_populates="reports")

    __table_args__ = (
        Index("ix_reports_doc_created", "document_id", "created_at"),
    )