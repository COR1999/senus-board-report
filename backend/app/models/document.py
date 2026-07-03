from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.financial_metrics import FinancialMetrics
    from app.models.report import Report


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="processing")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    financial_metrics: Mapped[Optional["FinancialMetrics"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reports: Mapped[List["Report"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )