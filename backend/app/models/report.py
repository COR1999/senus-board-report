"""Report model."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Report(Base):
    """AI-generated board report."""
    
    __tablename__ = "reports"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), unique=True, nullable=False)
    
    # AI content
    ai_commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships - use string reference
    document: Mapped["Document"] = relationship(
        "Document", 
        back_populates="report"
    )
    
    def __repr__(self):
        return f"<Report(id={self.id}, document_id={self.document_id})>"