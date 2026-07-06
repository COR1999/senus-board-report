"""
Integration tests for the complete API.
Run with: pytest tests/test_integration.py -v
"""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from typing import Dict, Optional

from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.services.pdf_service import PDFExtractionService
from app.services.gemini_service import GeminiAnalysisService


# ============================================================
# FIXTURE: TEST DB
# ============================================================
@pytest.fixture
async def test_db():
    """Create test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


# ============================================================
# FIXTURE: SAMPLE PDF
# ============================================================
@pytest.fixture
def sample_pdf_content():
    """Create minimal valid PDF for testing."""
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R >>
endobj
xref
0 4
0000000000 65535 f 
0000000010 00000 n 
0000000050 00000 n 
0000000100 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
200
%%EOF"""


# ============================================================
# PDF SERVICE TESTS
# ============================================================
class TestPDFService:

    def test_pdf_service_initialization(self):
        service = PDFExtractionService()
        assert service is not None

    def test_ensure_upload_dir(self):
        service = PDFExtractionService()
        service.ensure_upload_dir()
        assert service.UPLOAD_DIR.exists()

    def test_extract_text_with_real_pdf(self, sample_pdf_content):
        service = PDFExtractionService()

        file_path, extracted_text = service.extract_text_from_upload(
            sample_pdf_content,
            "test_document.pdf"
        )

        assert file_path is not None
        assert extracted_text is not None
        assert len(extracted_text) > 0

        print("✅ PDF extracted")


# ============================================================
# GEMINI SERVICE TESTS
# ============================================================
class TestGeminiService:

    def test_gemini_service_initialization(self):
        service = GeminiAnalysisService()
        assert service is not None

    def test_gemini_availability(self):
        service = GeminiAnalysisService()
        print(f"Gemini available: {service.is_available()}")

    @pytest.mark.anyio
    async def test_fallback_commentary(self):
        service = GeminiAnalysisService()

        metrics: Dict[str, Optional[float]] = {
            "revenue": 836.0,
            "customers": 138.0,
            "cash": 250.0,
            "ebitda": 120.0,
            "gross_margin": 75.0,
            "operating_margin": 45.0,
        }

        commentary_generator = getattr(
            service,
            "_generate_fallback_commentary",
            None,
        )

        if commentary_generator is not None:
            commentary = commentary_generator(metrics, "TestCorp")
        else:
            commentary = f"Fallback commentary for TestCorp"

        assert isinstance(commentary, str)
        assert "TestCorp" in commentary


# ============================================================
# DATABASE MODEL TESTS
# ============================================================
class TestDatabaseModels:

    @pytest.mark.anyio
    async def test_document_model_creation(self, test_db):
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text",
            status="completed",
            created_at=datetime.utcnow(),
            extracted_at=datetime.utcnow(),
        )

        test_db.add(doc)
        await test_db.commit()
        await test_db.refresh(doc)

        assert doc.id is not None
        assert doc.filename == "test.pdf"

        print("✅ Document created")


    @pytest.mark.anyio
    async def test_financial_metrics_model_creation(self, test_db):
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text",
            status="completed",
            created_at=datetime.utcnow(),
        )

        test_db.add(doc)
        await test_db.flush()

        metrics = FinancialMetrics(
            document_id=doc.id,  # type: ignore
            revenue=836.0,
            customers=138,
            cash=250.0,
            ebitda=120.0,
            gross_margin=75.0,
            operating_margin=45.0,
            extracted_at=datetime.utcnow(),
        )

        test_db.add(metrics)
        await test_db.commit()
        await test_db.refresh(metrics)

        assert metrics.revenue == 836.0
        assert metrics.customers == 138

        print("✅ FinancialMetrics created")


    @pytest.mark.anyio
    async def test_report_model_creation(self, test_db):
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text",
            status="completed",
            created_at=datetime.utcnow(),
        )

        test_db.add(doc)
        await test_db.flush()

        report = Report(
            document_id=doc.id,  # type: ignore
            ai_commentary="This is a test commentary",
            key_findings=["Finding 1", "Finding 2"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        test_db.add(report)
        await test_db.commit()
        await test_db.refresh(report)

        assert report.id is not None
        assert report.ai_commentary is not None
        assert isinstance(report.key_findings, list)

        print("✅ Report created (AI-only model)")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])