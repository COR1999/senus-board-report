"""Tests for GET /metrics/dashboard/summary, particularly the sparkline `history` field."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics


async def _add_metrics_row(
    session: AsyncSession,
    *,
    revenue=None,
    customers=None,
    cash=None,
    ebitda=None,
    extracted_at=None,
) -> FinancialMetrics:
    doc = Document(
        filename="test.pdf",
        status="completed",
        created_at=datetime.utcnow(),
    )
    session.add(doc)
    await session.flush()

    metrics = FinancialMetrics(
        document_id=doc.id,
        revenue=revenue,
        customers=customers,
        cash=cash,
        ebitda=ebitda,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)
    await session.flush()  # flush (not commit) -- async_client shares this session, and
    # conftest.py's async_session fixture rolls back at teardown for test isolation.
    return metrics


@pytest.mark.anyio
async def test_dashboard_summary_zero_rows(async_client, async_session):
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    for key in ("revenue", "customers", "cash", "ebitda"):
        assert body[key]["history"] == []
        assert body[key]["trend"] == "neutral"
        assert body[key]["change"] == 0


@pytest.mark.anyio
async def test_dashboard_summary_single_row(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0, customers=50, cash=20_000.0, ebitda=5_000.0)
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["revenue"]["history"] == [100_000.0]
    assert body["revenue"]["change"] == 0
    assert body["revenue"]["trend"] == "neutral"


@pytest.mark.anyio
async def test_dashboard_summary_history_capped_and_ordered(async_client, async_session):
    base = datetime(2026, 1, 1)
    for i in range(10):
        await _add_metrics_row(
            async_session,
            revenue=i * 100_000.0,
            customers=i * 10,
            cash=i * 1_000.0,
            ebitda=i * 500.0,
            extracted_at=base + timedelta(minutes=i),
        )
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    history = response.json()["revenue"]["history"]

    assert len(history) == 8
    assert history[-1] == 900_000.0  # latest row (i=9)
    assert history[0] == 200_000.0   # 8th-most-recent row (i=2), not the 10th (i=0)


@pytest.mark.anyio
async def test_dashboard_summary_preserves_null_for_missing_field(async_client, async_session):
    base = datetime(2026, 1, 1)
    await _add_metrics_row(async_session, revenue=100_000.0, customers=None, extracted_at=base)
    await _add_metrics_row(async_session, revenue=200_000.0, customers=20, extracted_at=base + timedelta(minutes=1))
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    history = response.json()["customers"]["history"]

    assert len(history) == 2
    assert history[0] is None
    assert history[1] == 20.0
