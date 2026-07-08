from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer

from app.core.database import Base


class HiddenExternalFiling(Base):
    """
    Investor-relations-API filings the user has explicitly marked as
    "not applicable"/out of scope (e.g. an AGM notice with no extractable
    financial data), so GET /api/documents/external/available stops
    re-listing it forever. A rejected import (422, confidence too low)
    creates no Document row by design (see extraction_confidence.py) --
    without this table, there was no way to distinguish "not yet reviewed"
    from "reviewed and confirmed out of scope," so a rejected filing kept
    cluttering the "new filings available" banner indefinitely.

    Metadata is snapshotted at hide-time (not re-fetched from the IR API on
    every read) so the "hidden" list stays stable and displayable even if
    the IR API later changes or stops listing that filing.
    """
    __tablename__ = "hidden_external_filings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attachment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hidden_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
