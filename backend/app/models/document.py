"""
Document SQLAlchemy model.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    """
    Document model for storing uploaded PDF files and extracted text.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    extracted_text = Column(Text, nullable=True)
    status = Column(String(50), default="processing", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extracted_at = Column(DateTime, nullable=True)

    # Relationships
    financial_metrics = relationship("FinancialMetrics", back_populates="document", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="document", cascade="all, delete-orphan")