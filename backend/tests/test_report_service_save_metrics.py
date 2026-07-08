"""
Tests for ReportService._save_metrics preserving `None` (genuinely missing)
rather than fabricating `0` for the four baseline fields (revenue, customers,
cash, ebitda).

Real-world incident this guards against: importing a non-financial document
(e.g. an AGM notice) via the investor-relations sync feature ran it through
this same save path. The extractor correctly found nothing, but this method
used to coerce that `None` into `0` -- producing a fake all-zero metrics row
that then outranked the real half-year filing's data as "the latest" on the
production dashboard.
"""
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.services.report_service import ReportService
import app.models  # noqa: F401 -- registers all models on Base.metadata


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


async def _make_document(session: AsyncSession) -> Document:
    doc = Document(filename="test.pdf", status="processing")
    session.add(doc)
    await session.flush()
    return doc


@pytest.mark.anyio
async def test_save_metrics_preserves_none_when_extraction_found_nothing(async_session):
    # Simulates a non-financial document: the deterministic extractor and
    # Gemini fallback both found none of the four baseline fields.
    doc = await _make_document(async_session)
    service = ReportService(async_session)

    await service._save_metrics(doc.id, {"financial_metrics": {}})

    saved = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == doc.id)
        )
    ).first()
    assert saved.revenue is None
    assert saved.customers is None
    assert saved.cash is None
    assert saved.ebitda is None


@pytest.mark.anyio
async def test_save_metrics_preserves_real_values(async_session):
    doc = await _make_document(async_session)
    service = ReportService(async_session)

    await service._save_metrics(
        doc.id,
        {
            "financial_metrics": {
                "revenue": 354_813.0,
                "customers": 138,
                "cash": 735_189.0,
                "ebitda": -473_739.0,
            }
        },
    )

    saved = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == doc.id)
        )
    ).first()
    assert saved.revenue == 354_813.0
    assert saved.customers == 138
    assert saved.cash == 735_189.0
    assert saved.ebitda == -473_739.0


@pytest.mark.anyio
async def test_save_metrics_handles_ai_wrapped_value_shape(async_session):
    # Gemini's response shape wraps each figure as {"value": N} rather than
    # a plain number -- both formats must be handled identically.
    doc = await _make_document(async_session)
    service = ReportService(async_session)

    await service._save_metrics(
        doc.id,
        {"financial_metrics": {"revenue": {"value": 100_000.0}, "customers": {"value": None}}},
    )

    saved = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == doc.id)
        )
    ).first()
    assert saved.revenue == 100_000.0
    assert saved.customers is None


def test_normalize_metric_preserves_none():
    service = ReportService.__new__(ReportService)  # skip __init__ (no Gemini client needed)
    assert service._normalize_metric(None) is None
    assert service._normalize_metric(None, force_int=True) is None
    assert service._normalize_metric("not a number") is None


def test_extract_metric_value_preserves_none():
    service = ReportService.__new__(ReportService)
    assert service._extract_metric_value(None) is None
    assert service._extract_metric_value({"value": None}) is None
    assert service._extract_metric_value({"value": 42}) == 42
    assert service._extract_metric_value(0) == 0
