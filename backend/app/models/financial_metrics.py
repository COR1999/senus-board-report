from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class FinancialMetrics(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), unique=True)
    revenue: Mapped[Optional[float]] = mapped_column(default=None)
    customers: Mapped[Optional[int]] = mapped_column(default=None)
    cash: Mapped[Optional[float]] = mapped_column(default=None)
    ebitda: Mapped[Optional[float]] = mapped_column(default=None)
    gross_margin: Mapped[Optional[float]] = mapped_column(default=None)
    operating_margin: Mapped[Optional[float]] = mapped_column(default=None)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    document: Mapped["Document"] = relationship(back_populates="financial_metrics")