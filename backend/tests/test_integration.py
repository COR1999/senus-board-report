"""
Integration tests for the complete API.
Run with: pytest tests/test_integration.py -v
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from typing import Dict, Any, Mapping, Optional, List, cast

from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report
from app.schemas.financial import DocumentWithText, FinancialMetricsResponse
from app.services.pdf_service import PDFExtractionService
from app.services.gemini_service import GeminiAnalysisService


# Fixtures for testing
@pytest.fixture
async def test_db():
    """Create test database."""
    # Use in-memory SQLite for testing
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


@pytest.fixture
def sample_pdf_content():
    """Create minimal valid PDF for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Sample PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000230 00000 n 
0000000309 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
403
%%EOF"""
    return pdf_content


# Test Cases

class TestPDFService:
    """Test PDF extraction service."""
    
    def test_pdf_service_initialization(self):
        """Test that PDF service initializes correctly."""
        service = PDFExtractionService()
        assert service is not None
        assert hasattr(service, 'extract_text_from_upload')
    
    def test_ensure_upload_dir(self):
        """Test upload directory creation."""
        service = PDFExtractionService()
        service.ensure_upload_dir()
        assert service.UPLOAD_DIR.exists()
    
    def test_extract_text_with_real_pdf(self, sample_pdf_content):
        """Test text extraction from PDF."""
        service = PDFExtractionService()
        
        # Extract text
        file_path, extracted_text = service.extract_text_from_upload(
            sample_pdf_content,
            "test_document.pdf"
        )
        
        # Verify results
        assert file_path is not None
        assert extracted_text is not None
        assert len(extracted_text) > 0
        assert "Sample PDF" in extracted_text
        
        print(f"✅ PDF extracted successfully")
        print(f"   File path: {file_path}")
        print(f"   Text length: {len(extracted_text)} chars")
        print(f"   Text preview: {extracted_text[:100]}...")


class TestGeminiService:
    """Test Gemini AI service."""
    
    def test_gemini_service_initialization(self):
        """Test that Gemini service initializes."""
        service = GeminiAnalysisService()
        assert service is not None
    
    def test_gemini_availability(self):
        """Check if Gemini API is available."""
        service = GeminiAnalysisService()
        is_available = service.is_available()
        print(f"✅ Gemini API available: {is_available}")
    
    @pytest.mark.anyio
    async def test_metric_extraction_fallback(self):
        """Test metric extraction without AI (regex-based)."""
        service = GeminiAnalysisService()

        sample_text = """
        Financial Report 2024

        Revenue: €836000
        Customers: 138
        Cash: €250000
        EBITDA: €120000
        Gross Margin: 75%
        Operating Margin: 45%
        """

        metrics = await service.extract_financial_metrics_from_text(
            sample_text,
            use_ai=False  # Use regex only
        )

        assert metrics["revenue"] == 836000.0
        assert metrics["customers"] == 138.0
        assert metrics["cash"] == 250000.0
        assert metrics["ebitda"] == 120000.0
        assert metrics["gross_margin"] == 75.0
        assert metrics["operating_margin"] == 45.0
    
    @pytest.mark.anyio
    async def test_fallback_commentary(self):
        """Test fallback commentary generation."""
        service = GeminiAnalysisService()
        
        metrics: Dict[str, Optional[float]] = {
            "revenue": 836.0,
            "customers": 138.0,
            "cash": 250.0,
            "ebitda": 120.0,
            "gross_margin": 75.0,
            "operating_margin": 45.0,
        }
        
        commentary = service._generate_fallback_commentary(metrics, "TestCorp")
        
        assert "TestCorp" in commentary
        assert len(commentary) > 50
        
        print(f"✅ Fallback commentary generated")
        print(f"   Length: {len(commentary)} chars")
    
    @pytest.mark.anyio
    async def test_fallback_summary(self):
        """Test fallback summary generation."""
        service = GeminiAnalysisService()
        
        metrics: Dict[str, Optional[float]] = {
            "revenue": 836.0,
            "customers": 138.0,
            "cash": 250.0,
            "ebitda": 120.0,
            "gross_margin": 75.0,
            "operating_margin": 45.0,
        }
        
        summary = service._generate_fallback_summary(metrics)
        
        assert isinstance(summary, (list, type(None)))
        if summary is not None:
            assert len(summary) > 0
            assert all(isinstance(item, str) for item in summary)
            
            print(f"✅ Fallback summary generated")
            print(f"   Bullets: {len(summary)}")
            for bullet in summary:
                print(f"     • {bullet}")


class TestDatabaseModels:
    """Test database models."""
    
    @pytest.mark.anyio
    async def test_document_model_creation(self, test_db):
        """Test creating a Document model."""
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text content",
            status="completed",
            created_at=datetime.utcnow(),
            extracted_at=datetime.utcnow(),
        )
        
        test_db.add(doc)
        await test_db.commit()
        await test_db.refresh(doc)
        
        assert doc.id is not None
        assert str(doc.filename) == "test.pdf"
        assert str(doc.status) == "completed"
        
        print(f"✅ Document model created")
        print(f"   ID: {doc.id}")
        print(f"   Filename: {doc.filename}")
    
    @pytest.mark.anyio
    async def test_financial_metrics_model_creation(self, test_db):
        """Test creating FinancialMetrics model."""
        # First create a document
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text",
            status="completed",
            created_at=datetime.utcnow(),
        )
        test_db.add(doc)
        await test_db.flush()
        
        # Create metrics
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
        
        assert metrics.id is not None
        assert metrics.revenue == 836.0
        assert metrics.customers == 138
        
        print(f"✅ FinancialMetrics model created")
        print(f"   ID: {metrics.id}")
        print(f"   Revenue: {metrics.revenue}K")
    
    @pytest.mark.anyio
    async def test_report_model_creation(self, test_db):
        """Test creating Report model."""
        # Create document first
        doc = Document(
            filename="test.pdf",
            extracted_text="Sample text",
            status="completed",
            created_at=datetime.utcnow(),
        )
        test_db.add(doc)
        await test_db.flush()
        
        # Create report
        report = Report(
            document_id=doc.id,  # type: ignore
            ai_commentary="This is a test commentary",
            summary={"key_findings": ["Finding 1", "Finding 2", "Finding 3"]},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        test_db.add(report)
        await test_db.commit()
        await test_db.refresh(report)
        
        assert report.id is not None
        assert report.ai_commentary == "This is a test commentary"
        assert report.summary is not None
        
        print(f"✅ Report model created")
        print(f"   ID: {report.id}")
        print(f"   Has commentary: {bool(report.ai_commentary)}")


# Run with: pytest tests/test_integration.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])