from __future__ import annotations

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB   # or keep JSON

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,           # One report per document (remove if you want multiple versions)
        index=True,
        nullable=False
    )

    # === Content fields ===
    ai_commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_findings: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)   # explicit bullet points
    summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)            # raw metrics / structured data

    # === Metadata ===
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)   # pending, completed, failed
    generation_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # gemini, fallback, manual
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    version: Mapped[int] = mapped_column(default=1, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="reports")

    __table_args__ = (
        Index("ix_reports_doc_created", "document_id", "created_at"),
    )