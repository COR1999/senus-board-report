"""
Tests for GET /api/documents/{id}/file.

Railway's filesystem is ephemeral (see backend/README.md) -- a document's
DB row and extracted text can be intact (Postgres persists independently)
while the raw PDF bytes on disk are gone after a redeploy/restart. This is
distinguished from "document not found" with a specific 404 message.
"""
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes.documents import download_document_file
from app.core.database import Base
from app.models.document import Document
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


@pytest.mark.anyio
async def test_downloading_a_nonexistent_document_returns_404(async_session):
    with pytest.raises(HTTPException) as exc_info:
        await download_document_file(999, async_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Document not found"


@pytest.mark.anyio
async def test_returns_a_specific_404_when_the_file_is_missing_from_disk(async_session, tmp_path):
    # Simulates the real Railway scenario: the DB row survived (Postgres),
    # but the file_path it points to doesn't exist on this instance's disk
    # (e.g. lost across a redeploy).
    missing_path = tmp_path / "uploads" / "gone.pdf"
    document = Document(
        filename="gone.pdf",
        file_path=str(missing_path),
        status="completed",
        created_at=datetime.utcnow(),
    )
    async_session.add(document)
    await async_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await download_document_file(document.id, async_session)

    assert exc_info.value.status_code == 404
    assert "no longer available" in exc_info.value.detail


@pytest.mark.anyio
async def test_returns_the_file_when_it_exists_on_disk(async_session, tmp_path):
    real_path = tmp_path / "real.pdf"
    real_path.write_bytes(b"%PDF-1.4 fake pdf bytes")

    document = Document(
        filename="real.pdf",
        file_path=str(real_path),
        status="completed",
        created_at=datetime.utcnow(),
    )
    async_session.add(document)
    await async_session.commit()

    response = await download_document_file(document.id, async_session)

    assert isinstance(response, FileResponse)
    assert Path(response.path) == real_path
    assert response.media_type == "application/pdf"
    assert response.filename == "real.pdf"
