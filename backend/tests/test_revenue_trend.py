"""Tests for GET /metrics/dashboard/revenue-trend."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics


async def _add_metrics_row(session: AsyncSession, *, revenue=None, extracted_at=None) -> FinancialMetrics:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    metrics = FinancialMetrics(
        document_id=doc.id,
        revenue=revenue,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)
    await session.flush()  # flush (not commit) -- see test_metrics_summary.py for why
    return metrics


@pytest.mark.anyio
async def test_revenue_trend_empty(async_client, async_session):
    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_revenue_trend_orders_oldest_to_newest(async_client, async_session):
    base = datetime(2025, 1, 15)
    await _add_metrics_row(async_session, revenue=100_000.0, extracted_at=base)
    await _add_metrics_row(async_session, revenue=200_000.0, extracted_at=base + timedelta(days=180))

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [
        {"period": "Jan 2025", "revenue": 100_000.0},
        {"period": "Jul 2025", "revenue": 200_000.0},
    ]


@pytest.mark.anyio
async def test_revenue_trend_caps_at_window(async_client, async_session):
    base = datetime(2020, 1, 1)
    for i in range(30):
        await _add_metrics_row(async_session, revenue=float(i), extracted_at=base + timedelta(days=30 * i))

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert len(points) == 24
    assert points[-1]["revenue"] == 29.0  # latest row
    assert points[0]["revenue"] == 6.0    # 24th-most-recent row, not the 30th


@pytest.mark.anyio
async def test_revenue_trend_preserves_null_for_missing_revenue(async_client, async_session):
    base = datetime(2025, 1, 1)
    await _add_metrics_row(async_session, revenue=None, extracted_at=base)
    await _add_metrics_row(async_session, revenue=50_000.0, extracted_at=base + timedelta(days=30))

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points[0]["revenue"] is None
    assert points[1]["revenue"] == 50_000.0
