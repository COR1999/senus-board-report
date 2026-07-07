from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class FinancialMetrics(Base):
    __tablename__ = "financial_metrics"
    __table_args__ = (
        Index("ix_financial_metrics_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    revenue: Mapped[Optional[float]] = mapped_column(default=None)
    customers: Mapped[Optional[int]] = mapped_column(default=None)
    cash: Mapped[Optional[float]] = mapped_column(default=None)
    ebitda: Mapped[Optional[float]] = mapped_column(default=None)
    gross_margin: Mapped[Optional[float]] = mapped_column(default=None)
    operating_margin: Mapped[Optional[float]] = mapped_column(default=None)

    # Prior-period comparative, extracted from the *same* filing's
    # comparative column (e.g. "Turnover 354,813 340,931" -- most
    # half-year/annual reports print the prior period right next to the
    # current one). Lets YoY change/trend be computed for a single filing
    # rather than only ever being 0%/neutral until a second document is
    # ever uploaded. No `customers_prior`: the one narrative customer
    # count in this filing is a fixed FY reference, not a period-over-period
    # comparative pair, so there's nothing real to store there.
    revenue_prior: Mapped[Optional[float]] = mapped_column(default=None)
    cash_prior: Mapped[Optional[float]] = mapped_column(default=None)
    ebitda_prior: Mapped[Optional[float]] = mapped_column(default=None)
    gross_margin_prior: Mapped[Optional[float]] = mapped_column(default=None)
    operating_margin_prior: Mapped[Optional[float]] = mapped_column(default=None)

    # Bookings -- narrative-regex extracted (same reliability class as
    # `customers`, not a structured table value), e.g. "pipeline deals of
    # approx. €700k across 21 enterprise customers closed in the period
    # (further approx. €500k of open pipeline)". No `_prior`: this filing
    # doesn't state a prior-period bookings comparative.
    bookings_value: Mapped[Optional[float]] = mapped_column(default=None)
    bookings_customers: Mapped[Optional[int]] = mapped_column(default=None)
    bookings_pipeline: Mapped[Optional[float]] = mapped_column(default=None)

    # Reporting period -- narrative-regex extracted directly from the
    # filing's own text (e.g. "(HY2026)" for the current period, "(HY25:"
    # for the recurring prior-year comparison label), NOT derived from
    # `extracted_at` (which is when we processed the upload, not the period
    # the filing covers) and NOT dependent on the AI/Gemini narrative path
    # (which is skipped whenever the deterministic baseline extraction is
    # already complete -- see report_service._baseline_is_complete). Labels
    # are stored verbatim as the filing states them, since real filings use
    # inconsistent formats (e.g. "HY2026" vs "HY25", not "H1 2026"/"H1 2025")
    # that a generic year-math derivation would get wrong.
    reporting_period: Mapped[Optional[str]] = mapped_column(default=None)
    reporting_period_prior: Mapped[Optional[str]] = mapped_column(default=None)

    # Calendar-month version of the above, e.g. "Dec 2025"/"Dec 2024" --
    # derived from the filing's own "ended DD Month YYYY" text. Used for
    # chart axis labels, which "HY2026" alone didn't make clear (Senus's
    # fiscal year runs Jul-Jun, so "HY" periods don't end in the month a
    # reader might assume).
    reporting_period_end: Mapped[Optional[str]] = mapped_column(default=None)
    reporting_period_end_prior: Mapped[Optional[str]] = mapped_column(default=None)

    extracted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationship back to the source document.
    document: Mapped["Document"] = relationship(back_populates="financial_metrics")