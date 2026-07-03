"""Financial metrics model."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


class FinancialMetrics(Base):
    """Financial metrics extracted from documents."""
    
    __tablename__ = "financial_metrics"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    
    # Financial data
    revenue: Mapped[float] = mapped_column(Float, nullable=False)
    customers: Mapped[int] = mapped_column(Integer, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    operating_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships - use string reference
    document: Mapped["Document"] = relationship(
        "Document", 
        back_populates="metrics"
    )
    
    def __repr__(self):
        return f"<FinancialMetrics(id={self.id}, revenue={self.revenue})>"