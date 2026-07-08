"""
Tests for checking Senus's investor relations API for new filings and
importing one on demand (GET/POST /api/documents/external/*).

Two layers: the low-level `investor_relations_client` (mocks `httpx`, never
hits the real API), and the route handlers (mock the client module directly,
same pattern as `test_document_dedup.py`'s `FakeReportService`).
"""
from io import BytesIO
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as documents_routes
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.services import investor_relations_client
import app.models  # noqa: F401 -- registers all models on Base.metadata


# ==================== investor_relations_client ====================

class _FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json_data = json_data
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """Stands in for `httpx.AsyncClient` -- records requested URLs and
    returns canned responses keyed by URL suffix."""

    def __init__(self, responses):
        self._responses = responses
        self.requested_urls = []

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, *args, **kwargs):
        self.requested_urls.append(url)
        for suffix, response in self._responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"Unexpected URL requested: {url}")


@pytest.mark.anyio
async def test_list_available_filings_merges_documents_and_reports_categories(monkeypatch):
    fake_client = _FakeAsyncClient(
        {
            "documents/all-documents": _FakeResponse(
                {"documents": [{"attachmentId": "doc-1", "fileName": "Info Doc.pdf", "fileSize": 100, "publishedDate": "2025-12-01"}]}
            ),
            "reports/all-documents": _FakeResponse(
                {"documents": [{"attachmentId": "rep-1", "fileName": "Half Year.pdf", "fileSize": 200, "publishedDate": "2026-03-19"}]}
            ),
        }
    )
    monkeypatch.setattr(investor_relations_client.httpx, "AsyncClient", fake_client)

    filings = await investor_relations_client.list_available_filings()

    assert {f["attachment_id"] for f in filings} == {"doc-1", "rep-1"}


@pytest.mark.anyio
async def test_find_filing_returns_none_when_not_present(monkeypatch):
    fake_client = _FakeAsyncClient(
        {
            "documents/all-documents": _FakeResponse({"documents": []}),
            "reports/all-documents": _FakeResponse({"documents": []}),
        }
    )
    monkeypatch.setattr(investor_relations_client.httpx, "AsyncClient", fake_client)

    assert await investor_relations_client.find_filing("missing-id") is None


@pytest.mark.anyio
async def test_download_filing_returns_raw_bytes(monkeypatch):
    fake_client = _FakeAsyncClient(
        {"documents/documents/doc-1": _FakeResponse(content=b"%PDF-1.4 fake bytes")}
    )
    monkeypatch.setattr(investor_relations_client.httpx, "AsyncClient", fake_client)

    content = await investor_relations_client.download_filing("doc-1")

    assert content == b"%PDF-1.4 fake bytes"


# ==================== routes ====================

@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    # Function-scoped, dedicated engine -- these routes commit for real, so
    # sharing conftest's session-scoped engine would leak rows across files.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


class FakeReportService:
    def __init__(self, db):
        self.db = db

    async def generate_report(self, document_id, force=False):
        metrics = FinancialMetrics(document_id=document_id, revenue=100_000.0)
        self.db.add(metrics)
        report = type("Report", (), {"id": 1, "status": "completed"})()
        return report


@pytest.fixture(autouse=True)
def _fake_pdf_parsing(monkeypatch):
    monkeypatch.setattr(
        documents_routes.pdf_service,
        "extract_text_from_upload",
        lambda content, filename: (f"/tmp/{filename}", "some extracted text"),
    )
    monkeypatch.setattr(documents_routes, "ReportService", FakeReportService)


_INFO_DOC = {
    "attachment_id": "info-doc-id",
    "file_name": "Senus PLC Information Document",
    "file_size": 1_056_649,
    "published_date": "2025-12-01",
}
_ADF_STATEMENTS = {
    "attachment_id": "adf-statements-id",
    "file_name": "ADF Farm Solutions Financial Statements.pdf",
    "file_size": 7_098_868,
    "published_date": "2025-06-30",
}
# Same underlying filing as an already-ingested Document, but listed under a
# second attachment_id -- the real API does this (confirmed this session).
_HALF_YEAR_DUPLICATE_LISTING = {
    "attachment_id": "half-year-duplicate-id",
    "file_name": "Half Year Results.pdf",
    "file_size": 500_000,
    "published_date": "2026-03-19",
}


@pytest.mark.anyio
async def test_available_excludes_a_filing_already_imported_by_attachment_id(async_session, monkeypatch):
    async_session.add(
        Document(filename="Info Doc (already imported).pdf", external_attachment_id="info-doc-id", status="completed")
    )
    await async_session.commit()

    monkeypatch.setattr(
        investor_relations_client, "list_available_filings", lambda: _as_list([_INFO_DOC, _ADF_STATEMENTS])
    )

    result = await documents_routes.list_available_external_filings(async_session)

    assert [f.attachment_id for f in result] == ["adf-statements-id"]


@pytest.mark.anyio
async def test_available_excludes_a_filing_matched_by_filename_even_with_a_different_attachment_id(
    async_session, monkeypatch
):
    # The half-year filing was originally manually uploaded, so its
    # `external_attachment_id` is NULL -- only a filename match can catch
    # its duplicate listing under a different attachment_id.
    async_session.add(Document(filename="Half Year Results.pdf", external_attachment_id=None, status="completed"))
    await async_session.commit()

    monkeypatch.setattr(
        investor_relations_client,
        "list_available_filings",
        lambda: _as_list([_HALF_YEAR_DUPLICATE_LISTING, _INFO_DOC]),
    )

    result = await documents_routes.list_available_external_filings(async_session)

    assert [f.attachment_id for f in result] == ["info-doc-id"]


@pytest.mark.anyio
async def test_available_returns_genuinely_new_filings_when_none_are_imported(async_session, monkeypatch):
    monkeypatch.setattr(
        investor_relations_client, "list_available_filings", lambda: _as_list([_INFO_DOC, _ADF_STATEMENTS])
    )

    result = await documents_routes.list_available_external_filings(async_session)

    assert {f.attachment_id for f in result} == {"info-doc-id", "adf-statements-id"}


@pytest.mark.anyio
async def test_available_returns_502_when_the_ir_api_is_unreachable(async_session, monkeypatch):
    async def _raise():
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(investor_relations_client, "list_available_filings", _raise)

    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.list_available_external_filings(async_session)

    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_import_creates_a_document_with_the_attachment_id_set(async_session, monkeypatch):
    monkeypatch.setattr(investor_relations_client, "find_filing", lambda attachment_id: _as_value(_INFO_DOC))
    monkeypatch.setattr(investor_relations_client, "download_filing", lambda attachment_id: _as_value(b"%PDF-1.4 fake"))

    response = await documents_routes.import_external_filing("info-doc-id", async_session)

    stored = await async_session.get(Document, response.id)
    assert stored.external_attachment_id == "info-doc-id"
    assert stored.filename.endswith(".pdf")


@pytest.mark.anyio
async def test_import_404s_on_an_unknown_attachment_id(async_session, monkeypatch):
    monkeypatch.setattr(investor_relations_client, "find_filing", lambda attachment_id: _as_value(None))

    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.import_external_filing("unknown-id", async_session)

    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_reimporting_the_same_filing_is_rejected_via_content_hash_dedup(async_session, monkeypatch):
    monkeypatch.setattr(investor_relations_client, "find_filing", lambda attachment_id: _as_value(_INFO_DOC))
    monkeypatch.setattr(investor_relations_client, "download_filing", lambda attachment_id: _as_value(b"%PDF-1.4 fake"))

    await documents_routes.import_external_filing("info-doc-id", async_session)

    with pytest.raises(HTTPException) as exc_info:
        await documents_routes.import_external_filing("info-doc-id", async_session)

    assert exc_info.value.status_code == 409


async def _as_list(value):
    return value


async def _as_value(value):
    return value
