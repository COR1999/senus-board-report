"""Document model."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, func  
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.financial_metrics import FinancialMetrics
    from app.models.report import Report

class Document(Base):
    """PDF document model."""
    
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    metrics: Mapped[list["FinancialMetrics"]] = relationship(
        "FinancialMetrics", 
        back_populates="document", 
        cascade="all, delete-orphan"
    )
    report: Mapped[Optional["Report"]] = relationship(
        "Report", 
        back_populates="document", 
        cascade="all, delete-orphan", 
        uselist=False
    )
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"