"""
Route-level tests for the extraction confidence gate -- unlike
test_document_dedup.py/test_investor_relations_sync.py (which fake out
ReportService entirely), these use the *real* ReportService/_generate so
the actual confidence-scoring wiring is exercised, with only
FinancialMetricsExtractor and GeminiAnalysisService mocked (no real PDF
parsing or network calls).
"""
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import UploadFile
from io import BytesIO
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as documents_routes
from app.api.routes import reports as reports_routes
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.services import financial_metrics_extractor as fme_module
from app.services import report_service as report_service_module
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


class _FakeGemini:
    """Stands in for GeminiAnalysisService -- never makes a real API call."""

    def __init__(self, *args, **kwargs):
        pass

    def generate_report(self, prompt):
        return {"financial_metrics": {}, "key_findings": [], "ai_commentary": "", "model_version": "fake"}


def _mock_extraction(monkeypatch, *, format_recognized: bool, baseline: dict):
    """
    Configures FinancialMetricsExtractor's real (module-level) methods to
    return controlled values, so a real ReportService._generate exercises
    the actual confidence-scoring wiring without needing real PDF text.
    """
    monkeypatch.setattr(fme_module.FinancialMetricsExtractor, "is_format_recognized", staticmethod(lambda text: format_recognized))
    monkeypatch.setattr(fme_module.FinancialMetricsExtractor, "extract", classmethod(lambda cls, text: dict(baseline)))
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor, "extract_balance_sheet", classmethod(lambda cls, text: {})
    )
    monkeypatch.setattr(
        fme_module.FinancialMetricsExtractor,
        "check_reconciliation",
        classmethod(lambda cls, text: {"pnl_reconciles": None, "cashflow_reconciles": None}),
    )
    monkeypatch.setattr(report_service_module, "GeminiAnalysisService", _FakeGemini)


_GOVERNANCE_DOC_BASELINE = {
    "revenue": None, "revenue_prior": None, "cash": None, "cash_prior": None,
    "ebitda": None, "ebitda_prior": None, "customers": None,
    "bookings_value": None, "bookings_customers": None, "bookings_pipeline": None,
    "reporting_period": None, "reporting_period_prior": None,
    "reporting_period_end": None, "reporting_period_end_prior": None,
    "reporting_period_start": None, "reporting_period_start_prior": None,
    "gross_margin": None, "gross_margin_prior": None,
    "operating_margin": None, "operating_margin_prior": None,
}

_REAL_FILING_BASELINE = {
    **_GOVERNANCE_DOC_BASELINE,
    "revenue": 354_813.0, "cash": 735_189.0, "ebitda": -473_739.0, "customers": 138,
    "reporting_period": "HY2026",
}


@pytest.fixture(autouse=True)
def _fake_pdf_parsing(monkeypatch):
    monkeypatch.setattr(
        documents_routes.pdf_service,
        "extract_text_from_upload",
        lambda content, filename: (f"/tmp/{filename}", "some extracted text"),
    )


@pytest.mark.anyio
async def test_upload_rejects_a_governance_document_with_422_but_keeps_it_for_review(async_session, monkeypatch):
    _mock_extraction(monkeypatch, format_recognized=False, baseline=_GOVERNANCE_DOC_BASELINE)

    upload_file = UploadFile(filename="agm-notice.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    with pytest.raises(Exception) as exc_info:
        await documents_routes.upload_document(upload_file, async_session)

    assert getattr(exc_info.value, "status_code", None) == 422
    assert "confidence" in exc_info.value.detail.lower()

    # The document is kept (reversed from this project's original PR #42
    # "persist nothing" policy) -- a human reviewing why an extraction
    # failed needs the attempted values and reasons on hand, not just this
    # one-time 422. Confirmed via a real route call, not just the model.
    documents = (await async_session.execute(Document.__table__.select())).all()
    assert len(documents) == 1

    metrics_row = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == documents[0].id)
        )
    ).first()
    assert metrics_row.extraction_confidence_tier == "rejected"
    assert metrics_row.extraction_confidence_reasons  # non-empty -- the actual point breakdown

    report_row = (
        await async_session.execute(
            Report.__table__.select().where(Report.document_id == documents[0].id)
        )
    ).first()
    assert report_row.status == "rejected"


@pytest.mark.anyio
async def test_import_external_filing_rejects_a_governance_document_with_422_but_keeps_it_for_review(async_session, monkeypatch):
    _mock_extraction(monkeypatch, format_recognized=False, baseline=_GOVERNANCE_DOC_BASELINE)

    async def _find_filing(attachment_id):
        return {"attachment_id": attachment_id, "file_name": "AGM Notice", "file_size": 1000, "published_date": None}

    async def _download_filing(attachment_id):
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(documents_routes.investor_relations_client, "find_filing", _find_filing)
    monkeypatch.setattr(documents_routes.investor_relations_client, "download_filing", _download_filing)

    with pytest.raises(Exception) as exc_info:
        await documents_routes.import_external_filing("agm-id", async_session)

    assert getattr(exc_info.value, "status_code", None) == 422

    documents = (await async_session.execute(Document.__table__.select())).all()
    assert len(documents) == 1


@pytest.mark.anyio
async def test_upload_of_a_real_filing_auto_accepts_and_stores_confidence(async_session, monkeypatch):
    _mock_extraction(monkeypatch, format_recognized=True, baseline=_REAL_FILING_BASELINE)

    upload_file = UploadFile(filename="half-year.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    response = await documents_routes.upload_document(upload_file, async_session)

    assert response.financial_metrics.extraction_confidence == 100.0
    assert response.financial_metrics.extraction_confidence_tier == "auto_accept"


@pytest.mark.anyio
async def test_upload_with_partial_deterministic_match_persists_as_needs_review(async_session, monkeypatch):
    # Format recognized, revenue found deterministically, but no secondary
    # field or period -- 40 + 30 = 70... below reject. Use a scenario that
    # actually lands in 85-94: revenue + secondary via baseline, no period.
    partial_baseline = {
        **_GOVERNANCE_DOC_BASELINE,
        "revenue": 100_000.0,
        "cash": 50_000.0,
    }
    _mock_extraction(monkeypatch, format_recognized=True, baseline=partial_baseline)

    upload_file = UploadFile(filename="partial.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    response = await documents_routes.upload_document(upload_file, async_session)

    # 40 (format) + 30 (revenue) + 15 (secondary) + 0 (no period) = 85
    assert response.financial_metrics.extraction_confidence == 85.0
    assert response.financial_metrics.extraction_confidence_tier == "needs_review"

    documents = (await async_session.execute(Document.__table__.select())).all()
    assert len(documents) == 1


@pytest.mark.anyio
async def test_report_name_falls_back_to_filename_when_gemini_returns_no_company_name(async_session, monkeypatch):
    # Real production bug: a document routed through the Gemini path (baseline
    # incomplete -- e.g. the Information Document's genuinely-undisclosed
    # EBITDA) whose Gemini response didn't include a company_name fell
    # through to the frontend's "Document #{id}" placeholder, since only the
    # baseline-complete branch had a filename fallback. `_mock_extraction`'s
    # `_FakeGemini` returns no company_name, matching that real scenario.
    partial_baseline = {**_GOVERNANCE_DOC_BASELINE, "revenue": 100_000.0, "cash": 50_000.0}
    _mock_extraction(monkeypatch, format_recognized=True, baseline=partial_baseline)

    upload_file = UploadFile(filename="Senus PLC Information Document.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    response = await documents_routes.upload_document(upload_file, async_session)

    report_result = await async_session.execute(Report.__table__.select().where(Report.id == response.report_id))
    report_row = report_result.first()
    assert report_row.summary["company_name"] == "Senus PLC Information Document.pdf"


@pytest.mark.anyio
async def test_regenerate_with_low_confidence_leaves_existing_report_untouched(async_session, monkeypatch):
    # First: a real filing succeeds normally.
    _mock_extraction(monkeypatch, format_recognized=True, baseline=_REAL_FILING_BASELINE)
    upload_file = UploadFile(filename="half-year.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    first_response = await documents_routes.upload_document(upload_file, async_session)
    original_revenue = first_response.financial_metrics.revenue
    assert original_revenue == 354_813.0

    # Then: regenerating with a now-broken extraction (simulating e.g. a
    # code regression, or the extractor being pointed at the wrong text)
    # must not silently overwrite the existing good data.
    _mock_extraction(monkeypatch, format_recognized=False, baseline=_GOVERNANCE_DOC_BASELINE)

    with pytest.raises(Exception) as exc_info:
        await reports_routes.regenerate_report(first_response.report_id, async_session)
    assert getattr(exc_info.value, "status_code", None) == 422

    # The original FinancialMetrics row must be completely unchanged.
    metrics_result = await async_session.execute(
        FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == first_response.id)
    )
    metrics_row = metrics_result.first()
    assert metrics_row.revenue == 354_813.0
    assert metrics_row.extraction_confidence_tier == "auto_accept"

    # The Report itself must also be restored, not left stuck at
    # "generating" or newly stamped "rejected" -- see
    # ReportService._generate's `persist_on_reject` (False for a
    # force=True regenerate specifically so this can't happen) and
    # reports.py's own previous_status restore.
    report_row = (
        await async_session.execute(Report.__table__.select().where(Report.id == first_response.report_id))
    ).first()
    assert report_row.status == "completed"


@pytest.mark.anyio
async def test_first_time_rejected_generation_via_generate_or_get_report_persists_for_review(async_session, monkeypatch):
    # Distinct from the upload-route test above -- exercises
    # generate_or_get_report/reports.py directly (a document that already
    # exists with completed text extraction, but has no Report yet), the
    # other first-time (force=False) caller of ReportService._generate.
    document = Document(
        filename="agm-notice.pdf", status="completed", created_at=datetime.utcnow(),
        extracted_at=datetime.utcnow(), extracted_text="some extracted text",
    )
    async_session.add(document)
    await async_session.flush()
    await async_session.commit()

    _mock_extraction(monkeypatch, format_recognized=False, baseline=_GOVERNANCE_DOC_BASELINE)

    with pytest.raises(Exception) as exc_info:
        await reports_routes.generate_or_get_report(document.id, async_session)
    assert getattr(exc_info.value, "status_code", None) == 422

    report_row = (
        await async_session.execute(Report.__table__.select().where(Report.document_id == document.id))
    ).first()
    assert report_row is not None
    assert report_row.status == "rejected"

    metrics_row = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == document.id)
        )
    ).first()
    assert metrics_row.extraction_confidence_tier == "rejected"


# ==================== POST /api/documents/{id}/approve ====================

async def _upload_needs_review_document(async_session, monkeypatch, filename: str = "partial.pdf"):
    """Same scenario as test_upload_with_partial_deterministic_match_persists_as_needs_review
    above -- reused here rather than re-deriving a fresh needs_review fixture."""
    partial_baseline = {**_GOVERNANCE_DOC_BASELINE, "revenue": 100_000.0, "cash": 50_000.0}
    _mock_extraction(monkeypatch, format_recognized=True, baseline=partial_baseline)
    upload_file = UploadFile(filename=filename, file=BytesIO(b"%PDF-1.4 fake"))
    return await documents_routes.upload_document(upload_file, async_session)


@pytest.mark.anyio
async def test_approve_promotes_a_needs_review_document_without_rewriting_its_score(async_session, monkeypatch):
    uploaded = await _upload_needs_review_document(async_session, monkeypatch)
    assert uploaded.financial_metrics.extraction_confidence_tier == "needs_review"

    approved = await documents_routes.approve_document(uploaded.id, async_session)

    # The API-facing tier now reads as auto_accept (no more "Pending
    # Review" tag anywhere it's shown)...
    assert approved.financial_metrics.extraction_confidence_tier == "auto_accept"
    # ...but the raw score is the same honest 85% the extractor actually
    # found -- approval doesn't fabricate a better score, only unlocks
    # dashboard eligibility via a separate column.
    assert approved.financial_metrics.extraction_confidence == 85.0

    metrics_row = (
        await async_session.execute(
            FinancialMetrics.__table__.select().where(FinancialMetrics.document_id == uploaded.id)
        )
    ).first()
    # The *raw* DB column is untouched -- still literally "needs_review",
    # a permanent, honest record of the algorithmic result. Only
    # human_approved_at changes.
    assert metrics_row.extraction_confidence_tier == "needs_review"
    assert metrics_row.human_approved_at is not None


@pytest.mark.anyio
async def test_approve_rejects_an_already_auto_accept_document_with_400(async_session, monkeypatch):
    _mock_extraction(monkeypatch, format_recognized=True, baseline=_REAL_FILING_BASELINE)
    upload_file = UploadFile(filename="half-year.pdf", file=BytesIO(b"%PDF-1.4 fake"))
    uploaded = await documents_routes.upload_document(upload_file, async_session)
    assert uploaded.financial_metrics.extraction_confidence_tier == "auto_accept"

    with pytest.raises(Exception) as exc_info:
        await documents_routes.approve_document(uploaded.id, async_session)

    assert getattr(exc_info.value, "status_code", None) == 400


@pytest.mark.anyio
async def test_approve_404s_for_a_document_with_no_extracted_metrics(async_session):
    with pytest.raises(Exception) as exc_info:
        await documents_routes.approve_document(999_999, async_session)

    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.anyio
async def test_approve_is_not_silently_idempotent_on_a_second_call(async_session, monkeypatch):
    # Once approved, the raw tier is still "needs_review" (by design -- see
    # the promotion test above), so a second approve call must succeed
    # again rather than 400 -- a double-click shouldn't error just because
    # the *effective* tier already reads as auto_accept.
    uploaded = await _upload_needs_review_document(async_session, monkeypatch)
    await documents_routes.approve_document(uploaded.id, async_session)

    approved_again = await documents_routes.approve_document(uploaded.id, async_session)

    assert approved_again.financial_metrics.extraction_confidence_tier == "auto_accept"
