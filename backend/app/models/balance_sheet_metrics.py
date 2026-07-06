from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class BalanceSheetMetrics(Base):
    """
    Balance-sheet/cash-flow-sourced metrics, separate from FinancialMetrics
    (the P&L snapshot) since they come from different statements. Powers
    Cash & Liquidity, Solvency & Leverage, and Returns metrics -- see
    backend/docs/metrics-expansion-plan.md.

    All fields follow the same None-means-missing convention as
    FinancialMetrics: a document that doesn't report a line gets None,
    never a fabricated 0. `_prior` columns are the same filing's own
    comparative-period column (see FinancialMetrics for why).
    """

    __tablename__ = "balance_sheet_metrics"
    __table_args__ = (
        Index("ix_balance_sheet_metrics_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Solvency & Leverage
    total_debt: Mapped[Optional[float]] = mapped_column(default=None)
    total_debt_prior: Mapped[Optional[float]] = mapped_column(default=None)
    interest_expense: Mapped[Optional[float]] = mapped_column(default=None)
    interest_expense_prior: Mapped[Optional[float]] = mapped_column(default=None)

    # Profitability inputs (feed computed EBITDA/margins in MetricsService)
    cost_of_sales: Mapped[Optional[float]] = mapped_column(default=None)
    cost_of_sales_prior: Mapped[Optional[float]] = mapped_column(default=None)
    administrative_expenses: Mapped[Optional[float]] = mapped_column(default=None)
    administrative_expenses_prior: Mapped[Optional[float]] = mapped_column(default=None)
    operating_result: Mapped[Optional[float]] = mapped_column(default=None)  # EBIT, signed: negative = loss
    operating_result_prior: Mapped[Optional[float]] = mapped_column(default=None)

    # Cash & Liquidity
    working_capital_change: Mapped[Optional[float]] = mapped_column(default=None)
    working_capital_change_prior: Mapped[Optional[float]] = mapped_column(default=None)
    net_cash_used_operating: Mapped[Optional[float]] = mapped_column(default=None)  # positive magnitude
    net_cash_used_operating_prior: Mapped[Optional[float]] = mapped_column(default=None)

    # Returns
    capital_employed: Mapped[Optional[float]] = mapped_column(default=None)
    capital_employed_prior: Mapped[Optional[float]] = mapped_column(default=None)

    extracted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="balance_sheet_metrics")
