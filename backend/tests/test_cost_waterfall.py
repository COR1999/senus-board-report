"""Tests for GET /metrics/dashboard/cost-waterfall."""
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics


async def _add_metrics_row(
    session: AsyncSession,
    *,
    revenue=None,
    ebitda=None,
    extracted_at=None,
) -> FinancialMetrics:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    metrics = FinancialMetrics(
        document_id=doc.id,
        revenue=revenue,
        ebitda=ebitda,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)
    await session.flush()
    return metrics


async def _add_balance_sheet_row(session: AsyncSession, document_id: int, **fields) -> BalanceSheetMetrics:
    bs = BalanceSheetMetrics(document_id=document_id, extracted_at=datetime.utcnow(), **fields)
    session.add(bs)
    await session.flush()
    return bs


@pytest.mark.anyio
async def test_cost_waterfall_zero_rows_is_unavailable(async_client, async_session):
    response = await async_client.get("/metrics/dashboard/cost-waterfall")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["revenue"] is None
    assert body["document_id"] is None


@pytest.mark.anyio
async def test_cost_waterfall_unavailable_without_a_balance_sheet_row(async_client, async_session):
    """Mirrors the real FY2025 Information Document -- a summary-table-only
    filing with revenue/EBITDA but no cost breakdown at all."""
    await _add_metrics_row(async_session, revenue=837_000.0, ebitda=150_000.0)

    response = await async_client.get("/metrics/dashboard/cost-waterfall")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["revenue"] is None
    assert body["cost_of_sales"] is None


@pytest.mark.anyio
async def test_cost_waterfall_unavailable_when_only_some_fields_are_disclosed(async_client, async_session):
    metrics = await _add_metrics_row(async_session, revenue=837_000.0, ebitda=150_000.0)
    # cost_of_sales present, but administrative_expenses/operating_result missing.
    await _add_balance_sheet_row(async_session, metrics.document_id, cost_of_sales=300_000.0)

    response = await async_client.get("/metrics/dashboard/cost-waterfall")

    assert response.json()["available"] is False


@pytest.mark.anyio
async def test_cost_waterfall_computes_gross_profit_and_da_when_fully_disclosed(async_client, async_session):
    metrics = await _add_metrics_row(async_session, revenue=837_000.0, ebitda=150_000.0)
    await _add_balance_sheet_row(
        async_session,
        metrics.document_id,
        cost_of_sales=300_000.0,
        administrative_expenses=450_000.0,
        operating_result=87_000.0,
    )

    response = await async_client.get("/metrics/dashboard/cost-waterfall")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["revenue"] == 837_000.0
    assert body["cost_of_sales"] == 300_000.0
    assert body["gross_profit"] == 537_000.0
    assert body["administrative_expenses"] == 450_000.0
    assert body["operating_result"] == 87_000.0
    # D&A = EBITDA - operating result (EBIT)
    assert body["depreciation_amortization"] == 63_000.0
    assert body["ebitda"] == 150_000.0
    assert body["document_id"] == metrics.document_id


@pytest.mark.anyio
async def test_cost_waterfall_respects_document_id_anchor(async_client, async_session):
    older = await _add_metrics_row(
        async_session, revenue=600_000.0, ebitda=50_000.0, extracted_at=datetime(2025, 1, 1)
    )
    await _add_balance_sheet_row(
        async_session, older.document_id,
        cost_of_sales=200_000.0, administrative_expenses=300_000.0, operating_result=40_000.0,
    )
    newer = await _add_metrics_row(
        async_session, revenue=837_000.0, ebitda=150_000.0, extracted_at=datetime(2025, 6, 1)
    )
    await _add_balance_sheet_row(
        async_session, newer.document_id,
        cost_of_sales=300_000.0, administrative_expenses=450_000.0, operating_result=87_000.0,
    )

    response = await async_client.get(f"/metrics/dashboard/cost-waterfall?document_id={older.document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == older.document_id
    assert body["revenue"] == 600_000.0


@pytest.mark.anyio
async def test_cost_waterfall_404s_for_a_nonexistent_document_id(async_client, async_session):
    await _add_metrics_row(async_session, revenue=837_000.0, ebitda=150_000.0)

    response = await async_client.get("/metrics/dashboard/cost-waterfall?document_id=999999")

    assert response.status_code == 404
