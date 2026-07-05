from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import documents as documents_routes
from app.api.routes.metrics import create_metrics
from app.core.database import Base
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.schemas.financial import FinancialMetricsCreate


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value


class FakeSession:
    def __init__(self):
        self.added = []
        self.metrics = []
        self.next_id = 1

    def add(self, obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = self.next_id
            self.next_id += 1
        self.added.append(obj)
        if isinstance(obj, FinancialMetrics):
            self.metrics.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None

    async def rollback(self):
        return None

    async def execute(self, stmt):
        return FakeResult(self.metrics[-1] if self.metrics else None)


class FakeReportService:
    def __init__(self, db):
        self.db = db

    async def generate_report(self, document_id, force=False):
        metrics = FinancialMetrics(
            document_id=document_id,
            revenue=1000000.0,
            customers=120,
            cash=250000.0,
            ebitda=200000.0,
            gross_margin=70.0,
            operating_margin=35.0,
        )
        self.db.add(metrics)
        report = type("Report", (), {"id": 42, "status": "completed"})()
        return report


@pytest.mark.anyio
async def test_upload_document_returns_financial_metrics(monkeypatch):
    fake_db = FakeSession()

    monkeypatch.setattr(documents_routes.pdf_service, "extract_text_from_upload", lambda content, filename: ("/tmp/test.pdf", "Revenue: €1M"))
    monkeypatch.setattr(documents_routes, "ReportService", FakeReportService)

    upload_file = UploadFile(filename="test.pdf", file=BytesIO(b"%PDF-1.4"))

    response = await documents_routes.upload_document(upload_file, fake_db)

    assert response.financial_metrics is not None
    assert response.financial_metrics.revenue == 1000000.0
    assert response.financial_metrics.customers == 120
    assert response.financial_metrics.cash == 250000.0


@pytest.mark.anyio
async def test_create_metrics_returns_404_for_missing_document():
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

    async with async_session() as db:
        with pytest.raises(HTTPException) as exc_info:
            await create_metrics(
                FinancialMetricsCreate(
                    document_id=9999,
                    revenue=1.0,
                    customers=1,
                    cash=1.0,
                    ebitda=1.0,
                    gross_margin=1.0,
                    operating_margin=1.0,
                ),
                db,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"

    await engine.dispose()
