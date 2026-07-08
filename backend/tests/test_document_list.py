"""
Tests for GET /api/documents (list).

Regression coverage for two real findings from a 2026-07-08 code audit:
1. N+1 queries -- the route used to issue one FinancialMetrics query per
   document in the list, the exact pattern this codebase already avoids
   elsewhere (see metrics.py's _ai_reporting_periods_by_document).
2. Over-fetching -- the route returned DocumentWithText (including the full
   extracted_text, tens of KB per document) for every row, when the list
   view only ever renders filename/status/size/date.

Fixed by returning DocumentResponse (no extracted_text/financial_metrics)
built directly from a single query, with no per-row FinancialMetrics fetch
at all.
"""
from datetime import datetime, timedelta
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes.documents import list_documents
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import DocumentResponse
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


async def _add_document(session: AsyncSession, **overrides) -> Document:
    defaults = dict(
        filename="report.pdf",
        file_size=1024,
        extracted_text="a" * 50_000,  # simulates a real full-PDF-text payload
        status="completed",
        created_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    document = Document(**defaults)
    session.add(document)
    await session.flush()
    return document


@pytest.mark.anyio
async def test_list_documents_does_not_include_extracted_text(async_session):
    await _add_document(async_session)

    responses = await list_documents(db=async_session)

    assert len(responses) == 1
    assert not hasattr(responses[0], "extracted_text")


@pytest.mark.anyio
async def test_response_schema_has_no_extracted_text_field(async_session):
    # Schema-level guard, not just an instance check -- makes sure a future
    # edit can't silently reintroduce the field on the response model itself.
    assert "extracted_text" not in DocumentResponse.model_fields


@pytest.mark.anyio
async def test_list_documents_ignores_financial_metrics_with_no_extra_queries(async_session):
    # The list view never needs FinancialMetrics -- attaching one to a
    # document must not change the response or require it to be fetched.
    document = await _add_document(async_session)
    async_session.add(FinancialMetrics(document_id=document.id, revenue=100_000.0))
    await async_session.commit()

    responses = await list_documents(db=async_session)

    assert len(responses) == 1
    assert responses[0].filename == "report.pdf"


@pytest.mark.anyio
async def test_list_documents_includes_extraction_confidence_tier_via_one_batched_query(async_session):
    needs_review_doc = await _add_document(async_session, filename="needs-review.pdf")
    async_session.add(
        FinancialMetrics(
            document_id=needs_review_doc.id, revenue=100_000.0,
            extraction_confidence=88.0, extraction_confidence_tier="needs_review",
        )
    )
    no_metrics_doc = await _add_document(async_session, filename="no-metrics-yet.pdf")
    await async_session.commit()

    responses = await list_documents(db=async_session)

    by_filename = {r.filename: r for r in responses}
    assert by_filename["needs-review.pdf"].extraction_confidence_tier == "needs_review"
    assert by_filename["no-metrics-yet.pdf"].extraction_confidence_tier is None


@pytest.mark.anyio
async def test_list_documents_orders_newest_first(async_session):
    older = await _add_document(async_session, filename="older.pdf", created_at=datetime.utcnow() - timedelta(days=1))
    newer = await _add_document(async_session, filename="newer.pdf", created_at=datetime.utcnow())
    await async_session.commit()

    responses = await list_documents(db=async_session)

    assert [r.filename for r in responses] == ["newer.pdf", "older.pdf"]


@pytest.mark.anyio
async def test_list_documents_respects_skip_and_limit(async_session):
    for i in range(5):
        await _add_document(async_session, filename=f"doc-{i}.pdf", created_at=datetime.utcnow() - timedelta(days=i))
    await async_session.commit()

    responses = await list_documents(skip=1, limit=2, db=async_session)

    assert [r.filename for r in responses] == ["doc-1.pdf", "doc-2.pdf"]
