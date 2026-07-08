"""Tests for GET/PUT /metrics/dashboard/historical-insight."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.historical_insight import HistoricalInsight


@pytest.fixture(autouse=True)
async def _cleanup_committed_rows(async_session: AsyncSession):
    """
    Unlike every other test file, these tests exercise a PUT endpoint that
    calls `db.commit()` -- and conftest.py's `async_session` fixture only
    `rollback()`s at teardown, which cannot undo an already-committed
    change. Left alone, this test file's own `_add_metrics_row` fixtures
    (added via `flush()`, never committed by the test itself) get
    permanently committed as a side effect of hitting the PUT endpoint,
    leaking real FinancialMetrics rows into every other test file that
    runs afterward in the same session-scoped in-memory database (confirmed
    directly: `test_revenue_trend.py`'s exact-count assertions broke when
    run after this file, because unrelated leaked rows showed up in its own
    `/metrics/dashboard/revenue-trend` results). Explicit teardown restores
    isolation regardless of which endpoints under test happen to commit.
    """
    yield
    await async_session.execute(delete(HistoricalInsight))
    await async_session.execute(delete(FinancialMetrics))
    await async_session.execute(delete(Document))
    await async_session.commit()


async def _add_metrics_row(
    session: AsyncSession,
    *,
    revenue=None,
    extracted_at=None,
) -> FinancialMetrics:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    metrics = FinancialMetrics(
        document_id=doc.id,
        revenue=revenue,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)
    await session.flush()
    return metrics


@pytest.mark.anyio
async def test_get_404s_when_nothing_has_ever_been_generated(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0)

    response = await async_client.get("/metrics/dashboard/historical-insight")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_put_creates_and_get_returns_it_when_data_is_unchanged(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0)

    put_response = await async_client.put(
        "/metrics/dashboard/historical-insight",
        json={
            "insight": {"text": "Revenue has grown steadily", "type": "trend", "action": "Keep it up"},
            "model_version": "gemini-2.5-flash",
        },
    )
    assert put_response.status_code == 200

    get_response = await async_client.get("/metrics/dashboard/historical-insight")

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["insight"] == {
        "text": "Revenue has grown steadily",
        "type": "trend",
        "action": "Keep it up",
        "category": None,
    }
    assert body["model_version"] == "gemini-2.5-flash"


@pytest.mark.anyio
async def test_get_404s_again_once_a_new_report_changes_the_underlying_data(async_client, async_session):
    base = datetime(2025, 1, 15)
    await _add_metrics_row(async_session, revenue=100_000.0, extracted_at=base)

    await async_client.put(
        "/metrics/dashboard/historical-insight",
        json={"insight": {"text": "Stale insight", "type": "trend"}, "model_version": "gemini-2.5-flash"},
    )
    assert (await async_client.get("/metrics/dashboard/historical-insight")).status_code == 200

    # A new report lands -- the underlying revenue-trend data set changes,
    # so the previously-generated insight no longer describes the current
    # picture and must be treated as stale (404, not silently served).
    await _add_metrics_row(async_session, revenue=200_000.0, extracted_at=base + timedelta(days=180))

    response = await async_client.get("/metrics/dashboard/historical-insight")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_put_upserts_replacing_the_prior_stored_result_not_appending(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0)

    await async_client.put(
        "/metrics/dashboard/historical-insight",
        json={"insight": {"text": "Old insight", "type": "trend"}, "model_version": "gemini-2.5-flash"},
    )
    response = await async_client.put(
        "/metrics/dashboard/historical-insight",
        json={"insight": {"text": "New insight", "type": "trend"}, "model_version": "gemini-2.5-flash"},
    )

    assert response.status_code == 200
    assert response.json()["insight"]["text"] == "New insight"

    from sqlalchemy import select

    result = await async_session.execute(select(HistoricalInsight))
    assert len(result.scalars().all()) == 1
