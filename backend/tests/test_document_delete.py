"""
Tests for DELETE /api/documents/{id}.

Regression coverage for a real bug found while manually verifying
feature/document-dedup against the real production DB: the route used a
bulk `delete(Document).where(...)` SQL statement, which bypasses the ORM's
`cascade="all, delete-orphan"` on Document's relationships (there's no
DB-level ON DELETE CASCADE foreign key). Deleting any document that actually
had FinancialMetrics/Report rows attached -- i.e. any successfully processed
document, the common case -- failed with a ForeignKeyViolationError. This
was never caught before because no test exercised deleting a document with
real child rows attached.
"""
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes.documents import delete_document
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
import app.models  # noqa: F401 -- registers all models on Base.metadata
from fastapi import HTTPException


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    # Isolated engine, same reasoning as test_document_dedup.py -- this
    # route does a real `db.commit()`.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.anyio
async def test_deletes_a_document_with_financial_metrics_and_a_report_attached(async_session):
    document = Document(filename="report.pdf", status="completed", created_at=datetime.utcnow())
    async_session.add(document)
    await async_session.flush()

    async_session.add(FinancialMetrics(document_id=document.id, revenue=100_000.0))
    async_session.add(Report(document_id=document.id, summary={}, status="completed"))
    await async_session.commit()

    response = await delete_document(document.id, async_session)

    assert response == {"message": "Deleted successfully"}


@pytest.mark.anyio
async def test_deleting_a_nonexistent_document_returns_404(async_session):
    with pytest.raises(HTTPException) as exc_info:
        await delete_document(999, async_session)

    assert exc_info.value.status_code == 404
