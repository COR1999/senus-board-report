"""
Tests for period_merge_service.py -- same-period document merging.

Real production incident: ADF Farm Solutions (vision-extracted) and the
Information Document (text-extracted) both genuinely report FY2025
(Jul 2024 - Jun 2025), independently appearing in the period selector with
identical labels and no way to tell them apart. These tests use the real
upload route (only FinancialMetricsExtractor mocked, same pattern as
test_extraction_confidence_routes.py) so the actual merge-detection wiring
in _ingest_document is exercised, not just the service function in isolation.
"""
from datetime import datetime
from typing import AsyncGenerator
from io import BytesIO

import pytest
import pytest_asyncio
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as documents_routes
from app.api.routes import metrics as metrics_routes
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.services import financial_metrics_extractor as fme_module
from app.services import period_merge_service
from app.services import report_service as report_service_module
import app.models  # noqa: F401 -- registers all models on Base.metadata

_SAME_PERIOD = {"reporting_period_start": "Jul 2024", "reporting_period_end": "Jun 2025"}


class _FakeGemini:
    """Stands in for GeminiAnalysisService -- never makes a real API call.
    These test baselines deliberately leave gaps (missing customers/EBITDA,
    simulating two complementary real-world extractions), which makes
    _baseline_is_complete() False and would otherwise trigger a real Gemini
    call -- same reasoning/pattern as test_extraction_confidence_routes.py's
    own _FakeGemini."""

    def __init__(self, *args, **kwargs):
        pass

    def generate_report(self, prompt):
        return {"financial_metrics": {}, "key_findings": [], "ai_commentary": "", "model_version": "fake"}


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def _fake_pdf_parsing(monkeypatch):
    monkeypatch.setattr(
        documents_routes.pdf_service,
        "extract_text_from_upload",
        lambda content, filename: (f"/tmp/{filename}", "some extracted text"),
    )
    monkeypatch.setattr(report_service_module, "GeminiAnalysisService", _FakeGemini)


def _mock_extraction(monkeypatch, baseline: dict):
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor, "is_format_recognized", staticmethod(lambda text: True)
    )
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor, "extract", classmethod(lambda cls, text: dict(baseline))
    )
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor,
        "check_reconciliation",
        staticmethod(lambda text: {"pnl_reconciles": None, "cashflow_reconciles": None}),
    )
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor, "extract_balance_sheet", staticmethod(lambda text: {})
    )


async def _upload(async_session, monkeypatch, *, filename: str, baseline: dict):
    _mock_extraction(monkeypatch, baseline)
    upload_file = UploadFile(filename=filename, file=BytesIO(f"%PDF-1.4 {filename}".encode()))
    return await documents_routes.upload_document(upload_file, async_session)


@pytest.mark.anyio
async def test_ingest_merges_a_clean_gap_fill_with_no_conflicts(async_session, monkeypatch):
    # Doc A: has EBITDA, no customers (like ADF Farm Solutions).
    doc_a = await _upload(
        async_session, monkeypatch,
        filename="doc-a.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "cash": 140_135.0, "ebitda": -613_313.0, "customers": None},
    )
    # Doc B: same revenue/cash (agrees), has customers, no EBITDA (like the Information Document).
    doc_b = await _upload(
        async_session, monkeypatch,
        filename="doc-b.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "cash": 140_135.0, "ebitda": None, "customers": 36},
    )

    # Both originals are superseded by a new, third document.
    metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id.in_([doc_a.id, doc_b.id]))
    )
    original_rows = {row.document_id: row for row in metrics_result.all()}
    assert original_rows[doc_a.id].superseded_by_document_id is not None
    assert original_rows[doc_b.id].superseded_by_document_id is not None
    merged_document_id = original_rows[doc_a.id].superseded_by_document_id
    assert merged_document_id == original_rows[doc_b.id].superseded_by_document_id

    merged_metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == merged_document_id)
    )
    merged = merged_metrics_result.first()
    assert merged.revenue == 836_991.0
    assert merged.cash == 140_135.0
    assert merged.ebitda == -613_313.0  # filled in from doc A
    assert merged.customers == 36  # filled in from doc B
    assert merged.extraction_confidence_tier == "auto_accept"  # no conflicts

    merged_doc_result = await async_session.execute(
        Document.__table__.select().where(Document.id == merged_document_id)
    )
    merged_doc = merged_doc_result.first()
    assert "doc-a.pdf" in merged_doc.filename
    assert "doc-b.pdf" in merged_doc.filename
    assert merged_doc.file_path is None


@pytest.mark.anyio
async def test_ingest_merge_with_a_genuine_conflict_flags_needs_review(async_session, monkeypatch):
    # Both baselines include a matching `cash` value (no conflict there) so
    # each upload individually scores a full 100% (auto_accept) on its
    # own -- find_same_period_match only ever matches against an already-
    # eligible row, so the test needs the *pre-merge* uploads themselves to
    # qualify, with revenue as the one deliberately conflicting field.
    doc_a = await _upload(
        async_session, monkeypatch,
        filename="conflict-a.pdf",
        baseline={**_SAME_PERIOD, "revenue": 100_000.0, "cash": 50_000.0, "ebitda": None, "customers": None},
    )
    doc_b = await _upload(
        async_session, monkeypatch,
        filename="conflict-b.pdf",
        baseline={**_SAME_PERIOD, "revenue": 200_000.0, "cash": 50_000.0, "ebitda": None, "customers": None},
    )

    metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == doc_a.id)
    )
    merged_document_id = metrics_result.first().superseded_by_document_id
    assert merged_document_id is not None

    merged_metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == merged_document_id)
    )
    merged = merged_metrics_result.first()

    assert merged.extraction_confidence_tier == "needs_review"
    assert merged.revenue == 100_000.0  # existing (first-seen) source's value used provisionally
    reasons_text = " ".join(merged.extraction_confidence_reasons)
    assert "100000" in reasons_text.replace(",", "").replace(".0", "")
    assert "200000" in reasons_text.replace(",", "").replace(".0", "")
    assert "conflict-a.pdf" in reasons_text
    assert "conflict-b.pdf" in reasons_text
    assert doc_b.id  # sanity: second upload succeeded despite the eventual conflict flag


@pytest.mark.anyio
async def test_documents_with_different_periods_are_never_merged(async_session, monkeypatch):
    await _upload(
        async_session, monkeypatch,
        filename="hy2026.pdf",
        baseline={"reporting_period_start": "Jul 2025", "reporting_period_end": "Dec 2025", "revenue": 354_813.0},
    )
    doc_b = await _upload(
        async_session, monkeypatch,
        filename="fy2025.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0},
    )

    metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == doc_b.id)
    )
    assert metrics_result.first().superseded_by_document_id is None


@pytest.mark.anyio
async def test_dashboard_periods_shows_one_entry_not_two_after_a_merge(async_session, monkeypatch):
    await _upload(
        async_session, monkeypatch,
        filename="doc-a.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "customers": None},
    )
    await _upload(
        async_session, monkeypatch,
        filename="doc-b.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "customers": 36},
    )

    periods = await metrics_routes.get_dashboard_periods(db=async_session)

    assert len(periods) == 1


@pytest.mark.anyio
async def test_reconcile_all_periods_is_idempotent(async_session, monkeypatch):
    doc_a = await _upload(
        async_session, monkeypatch,
        filename="doc-a.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "cash": 140_135.0, "customers": None},
    )
    doc_b = await _upload(
        async_session, monkeypatch,
        filename="doc-b.pdf",
        baseline={**_SAME_PERIOD, "revenue": 836_991.0, "cash": 140_135.0, "customers": 36},
    )

    # Ingest-time merging already handled this pair -- reconcile finds nothing new to do.
    first_pass = await period_merge_service.reconcile_all_periods(async_session)
    assert first_pass == []

    second_pass = await period_merge_service.reconcile_all_periods(async_session)
    assert second_pass == []

    # Still exactly one merged document, not two.
    all_docs = (await async_session.execute(Document.__table__.select())).all()
    merged_filenames = [d.filename for d in all_docs if "merged" in d.filename]
    assert len(merged_filenames) == 1
