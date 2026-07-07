"""
Tests for exact-duplicate-upload detection on POST /api/documents/upload.

Uploading the same PDF twice previously created two separate Document rows
with no way to tell them apart -- there was no unique constraint on
filename/content and no dedup check in the upload route at all. Duplicates
are now detected by hashing the raw uploaded bytes (not the filename, which
would both false-positive on two different files sharing a name and
false-negative on a renamed re-upload of the same file).
"""
from io import BytesIO
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as documents_routes
from app.core.database import Base
from app.models.financial_metrics import FinancialMetrics
import app.models  # noqa: F401 -- registers all models on Base.metadata


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    # A fresh, function-scoped engine (not the shared session-scoped one in
    # conftest.py) -- the upload route does a real `db.commit()` on success
    # (by design, unlike most other routes' test helpers which only
    # `flush()`), which would otherwise leak committed Document rows into
    # every other test file sharing conftest's session-scoped engine.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


class FakeReportService:
    """Avoids exercising the real Gemini/extraction pipeline -- this test
    only cares about the upload route's dedup behavior."""

    def __init__(self, db):
        self.db = db

    async def generate_report(self, document_id, force=False):
        metrics = FinancialMetrics(document_id=document_id, revenue=100_000.0)
        self.db.add(metrics)
        report = type("Report", (), {"id": 1, "status": "completed"})()
        return report


@pytest.fixture(autouse=True)
def _fake_pdf_parsing(monkeypatch):
    # Every test in this file uploads byte strings that aren't real PDFs --
    # skip PyMuPDF entirely, same pattern as test_upload_metrics.py.
    monkeypatch.setattr(
        documents_routes.pdf_service,
        "extract_text_from_upload",
        lambda content, filename: (f"/tmp/{filename}", "some extracted text"),
    )
    monkeypatch.setattr(documents_routes, "ReportService", FakeReportService)


@pytest.mark.anyio
async def test_uploading_the_same_file_twice_is_rejected(async_session):
    content = b"identical PDF bytes"
    first = UploadFile(filename="report.pdf", file=BytesIO(content))
    await documents_routes.upload_document(first, async_session)

    second = UploadFile(filename="report.pdf", file=BytesIO(content))
    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.upload_document(second, async_session)

    assert exc_info.value.status_code == 409
    assert "already uploaded" in exc_info.value.detail


@pytest.mark.anyio
async def test_uploading_the_same_content_under_a_different_filename_is_still_rejected(async_session):
    # Dedup is content-based, not filename-based -- a renamed copy of the
    # same PDF must still be caught.
    content = b"identical PDF bytes, renamed"
    first = UploadFile(filename="original.pdf", file=BytesIO(content))
    await documents_routes.upload_document(first, async_session)

    renamed = UploadFile(filename="renamed-copy.pdf", file=BytesIO(content))
    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.upload_document(renamed, async_session)

    assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_two_different_files_sharing_a_filename_both_succeed(async_session):
    # Filename-only dedup would have false-positived here -- content differs,
    # so both uploads must succeed.
    first = UploadFile(filename="report.pdf", file=BytesIO(b"first file content"))
    second = UploadFile(filename="report.pdf", file=BytesIO(b"second, different content"))

    first_response = await documents_routes.upload_document(first, async_session)
    second_response = await documents_routes.upload_document(second, async_session)

    assert first_response.id != second_response.id


@pytest.mark.anyio
async def test_rejects_non_pdf_filename_with_400_not_500(async_session):
    # Regression guard: HTTPException is itself an Exception subclass, so a
    # bare `except Exception` below this raise would previously re-wrap it
    # as a 500 "Upload failed" instead of preserving the real 400.
    upload_file = UploadFile(filename="report.docx", file=BytesIO(b"not a pdf"))

    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.upload_document(upload_file, async_session)

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_rejects_empty_file_with_400_not_500(async_session):
    upload_file = UploadFile(filename="empty.pdf", file=BytesIO(b""))

    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.upload_document(upload_file, async_session)

    assert exc_info.value.status_code == 400
