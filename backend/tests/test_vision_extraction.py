"""
Tests for the vision-extraction backup path in ReportService._generate --
used only for a document with no text layer at all (a scanned PDF, e.g.
ADF Farm Solutions' statements). Confirms: the deterministic extractor is
never even attempted (there's nothing for it to parse), Gemini vision is
called exactly once with every page image, the result is tagged
generation_source="vision", and -- critically -- the confidence tier is
capped at needs_review even for a complete, well-formed vision extraction,
since there's no independent deterministic cross-check possible for a
scanned document.
"""
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.document import Document
from app.models.report import Report
from app.services.report_service import ReportService
import app.models  # noqa: F401 -- registers all models on Base.metadata

FIXTURE = Path(__file__).parent / "fixtures" / "ADF_Farm_Solutions_Financial_Statements_Jun2025.pdf"


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


async def _make_scanned_document_and_report(session: AsyncSession) -> tuple[Document, Report]:
    # extracted_text="" is the real shape for a scanned PDF -- confirmed
    # directly against this fixture (PyMuPDF's get_text() returns nothing
    # on every page).
    doc = Document(filename="ADF Farm Solutions.pdf", file_path=str(FIXTURE), extracted_text="", status="completed")
    session.add(doc)
    await session.flush()

    report = Report(document_id=doc.id, status="generating")
    session.add(report)
    await session.flush()

    return doc, report


@pytest.mark.anyio
async def test_a_complete_vision_extraction_is_persisted_but_capped_at_needs_review(async_session, monkeypatch):
    doc, report = await _make_scanned_document_and_report(async_session)
    service = ReportService(async_session)

    calls = []

    def fake_generate_report_from_images(images, context):
        calls.append((images, context))
        return {
            "company_name": "ADF Farm Solutions",
            "reporting_period": "FY2025",
            "financial_metrics": {
                "revenue": {"value": 500_000},
                "cash": {"value": 100_000},
            },
            "key_findings": ["Revenue grew year over year."],
            "ai_commentary": "Solid year of growth.",
        }

    monkeypatch.setattr(service.gemini, "generate_report_from_images", fake_generate_report_from_images)

    result = await service._generate(doc, report)

    # Gemini vision was called exactly once, with every page image from
    # the real 23-page scanned fixture.
    assert len(calls) == 1
    assert len(calls[0][0]) == 23
    assert calls[0][1] == "ADF Farm Solutions.pdf"

    assert result.status == "completed"
    assert result.generation_source == "vision"
    assert result.model_version == "gemini-vision"

    from app.models.financial_metrics import FinancialMetrics
    from sqlalchemy import select

    metrics = (
        await async_session.execute(select(FinancialMetrics).where(FinancialMetrics.document_id == doc.id))
    ).scalars().first()

    assert metrics.revenue == 500_000.0
    assert metrics.cash == 100_000.0
    # Never auto_accept for a scanned document, no matter how complete the
    # extraction -- always needs a human to confirm it first.
    assert metrics.extraction_confidence_tier == "needs_review"


@pytest.mark.anyio
async def test_a_scanned_document_never_reaches_the_deterministic_extractor(async_session, monkeypatch):
    # There's no text at all to parse -- the deterministic extractor must
    # never even be invoked for a scanned document (calling it would just
    # waste time re-confirming what's already known: nothing to find).
    doc, report = await _make_scanned_document_and_report(async_session)
    service = ReportService(async_session)

    monkeypatch.setattr(
        service.gemini, "generate_report_from_images",
        lambda images, context: {"financial_metrics": {}},
    )

    import app.services.financial_metrics_extractor as extractor_module

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("FinancialMetricsExtractor.extract must not be called for a scanned document")

    monkeypatch.setattr(extractor_module.FinancialMetricsExtractor, "extract", staticmethod(_fail_if_called))

    from app.services.extraction_confidence import LowConfidenceExtractionError

    # A weak extraction (nothing found) is correctly rejected -- confirms
    # the assertion above didn't just get silently skipped by an early
    # return (if FinancialMetricsExtractor.extract HAD been called, the
    # AssertionError above would surface here as an unrelated failure
    # instead of this expected LowConfidenceExtractionError).
    with pytest.raises(LowConfidenceExtractionError):
        await service._generate(doc, report)


@pytest.mark.anyio
async def test_a_failed_vision_extraction_is_rejected_and_persists_nothing(async_session, monkeypatch):
    doc, report = await _make_scanned_document_and_report(async_session)
    service = ReportService(async_session)

    # Simulates Gemini being unavailable/exhausted -- the real
    # _empty_response() shape from gemini_service.py.
    monkeypatch.setattr(
        service.gemini, "generate_report_from_images",
        lambda images, context: {
            "company_name": None, "reporting_period": None,
            "financial_metrics": {"revenue": None, "cash": None, "ebitda": None, "customers": None},
            "key_findings": [], "ai_commentary": "AI unavailable or failed (safe fallback).",
            "model_version": "gemini-unavailable",
        },
    )

    from app.services.extraction_confidence import LowConfidenceExtractionError

    with pytest.raises(LowConfidenceExtractionError):
        await service._generate(doc, report)
