from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.financial_metrics import FinancialMetrics
    from app.models.balance_sheet_metrics import BalanceSheetMetrics
    from app.models.report import Report


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # SHA256 hex digest of the uploaded file's raw bytes -- identifies an
    # exact duplicate re-upload regardless of filename (a renamed copy of the
    # same PDF still matches; two different PDFs that happen to share a
    # filename don't). Nullable + unique: existing rows keep NULL until
    # re-processed, which Postgres allows without breaking the constraint.
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    # Senus investor-relations API's attachmentId, set only for documents
    # imported via GET/POST /api/documents/external/* -- NULL for manually
    # uploaded documents. Lets the "available filings" check tell which IR
    # filings are already in the system without re-downloading/re-hashing
    # every candidate just to check.
    external_attachment_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="processing")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # One document can carry one metrics snapshot and multiple report versions.
    financial_metrics: Mapped[Optional["FinancialMetrics"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False
    )
    balance_sheet_metrics: Mapped[Optional["BalanceSheetMetrics"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False
    )
    reports: Mapped[List["Report"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )