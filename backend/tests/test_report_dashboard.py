"""Tests for GET /api/reports/{report_id}/dashboard."""
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.report import Report
from app.models.financial_metrics import FinancialMetrics


async def _add_report(session: AsyncSession, *, with_metrics: bool) -> Report:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    if with_metrics:
        session.add(FinancialMetrics(document_id=doc.id, revenue=100_000.0, customers=12))

    report = Report(document_id=doc.id, status="completed", key_findings=[])
    session.add(report)
    await session.flush()
    return report


@pytest.mark.anyio
async def test_report_dashboard_uses_none_not_zero_without_a_metrics_row(async_client, async_session):
    """A report with no FinancialMetrics row at all must report every
    figure as `None`, never a fabricated `0` -- the exact missing-vs-zero
    incident this project has guarded against everywhere else (see
    docs/roadmap.md, PRs #40-42)."""
    report = await _add_report(async_session, with_metrics=False)

    response = await async_client.get(f"/api/reports/{report.id}/dashboard")

    assert response.status_code == 200
    body = response.json()["financial_metrics"]
    assert body == {
        "revenue": None,
        "customers": None,
        "cash": None,
        "ebitda": None,
        "gross_margin": None,
        "operating_margin": None,
    }


@pytest.mark.anyio
async def test_report_dashboard_returns_real_figures_when_a_metrics_row_exists(async_client, async_session):
    report = await _add_report(async_session, with_metrics=True)

    response = await async_client.get(f"/api/reports/{report.id}/dashboard")

    assert response.status_code == 200
    body = response.json()["financial_metrics"]
    assert body["revenue"] == 100_000.0
    assert body["customers"] == 12
