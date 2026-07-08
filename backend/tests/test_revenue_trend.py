"""Tests for GET /metrics/dashboard/revenue-trend."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report


async def _add_metrics_row(
    session: AsyncSession,
    *,
    revenue=None,
    revenue_prior=None,
    ebitda=None,
    ebitda_prior=None,
    cash=None,
    cash_prior=None,
    extracted_at=None,
    fm_reporting_period=None,
    fm_reporting_period_prior=None,
    fm_reporting_period_end=None,
    fm_reporting_period_end_prior=None,
    ai_reporting_period=None,
) -> FinancialMetrics:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    metrics = FinancialMetrics(
        document_id=doc.id,
        revenue=revenue,
        revenue_prior=revenue_prior,
        ebitda=ebitda,
        ebitda_prior=ebitda_prior,
        cash=cash,
        cash_prior=cash_prior,
        reporting_period=fm_reporting_period,
        reporting_period_prior=fm_reporting_period_prior,
        reporting_period_end=fm_reporting_period_end,
        reporting_period_end_prior=fm_reporting_period_end_prior,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)

    if ai_reporting_period is not None:
        session.add(Report(document_id=doc.id, summary={"reporting_period": ai_reporting_period}, status="completed"))

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
    first = await _add_metrics_row(async_session, revenue=100_000.0, extracted_at=base)
    second = await _add_metrics_row(async_session, revenue=200_000.0, extracted_at=base + timedelta(days=180))

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [
        {
            "period": "Jan 2025", "revenue": 100_000.0, "ebitda": None, "cash": None,
            "document_id": first.document_id, "cadence_months": None,
        },
        {
            "period": "Jul 2025", "revenue": 200_000.0, "ebitda": None, "cash": None,
            "document_id": second.document_id, "cadence_months": None,
        },
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


@pytest.mark.anyio
async def test_revenue_trend_prefers_deterministic_period_over_extracted_at(async_client, async_session):
    # extracted_at is when we *processed* the upload, not the period the
    # filing covers -- a document processed today but reporting on "HY2026"
    # should show "HY2026" on the chart, not today's month/year.
    row = await _add_metrics_row(
        async_session,
        revenue=100_000.0,
        extracted_at=datetime(2026, 7, 6),
        fm_reporting_period="HY2026",
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [{
        "period": "HY2026", "revenue": 100_000.0, "ebitda": None, "cash": None,
        "document_id": row.document_id, "cadence_months": None,
    }]


@pytest.mark.anyio
async def test_revenue_trend_falls_back_to_ai_reporting_period(async_client, async_session):
    # No deterministic FinancialMetrics.reporting_period -- falls back to
    # the AI-extracted Report.summary field before extracted_at.
    row = await _add_metrics_row(
        async_session,
        revenue=100_000.0,
        extracted_at=datetime(2026, 7, 6),
        ai_reporting_period="H1 2025",
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [{
        "period": "H1 2025", "revenue": 100_000.0, "ebitda": None, "cash": None,
        "document_id": row.document_id, "cadence_months": None,
    }]


@pytest.mark.anyio
async def test_revenue_trend_falls_back_to_extracted_at_without_a_report(async_client, async_session):
    row = await _add_metrics_row(async_session, revenue=100_000.0, extracted_at=datetime(2025, 3, 1))

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    assert response.json() == [{
        "period": "Mar 2025", "revenue": 100_000.0, "ebitda": None, "cash": None,
        "document_id": row.document_id, "cadence_months": None,
    }]


@pytest.mark.anyio
async def test_revenue_trend_prepends_embedded_prior_point_with_only_one_document(async_client, async_session):
    """
    Regression test: the KPI card's own sparkline/change% already uses the
    filing's embedded revenue_prior (see get_dashboard_metrics), so a single
    uploaded document showing "+4.1% vs prior period" on the card while this
    chart renders one flat point read as if the delta were fabricated. With
    only one document, the chart must plot the same two real points the
    card's percentage is computed from.
    """
    row = await _add_metrics_row(
        async_session,
        revenue=354_813.0,
        revenue_prior=340_931.0,
        fm_reporting_period="HY2026",
        fm_reporting_period_prior="HY25",
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    assert response.json() == [
        {"period": "HY25", "revenue": 340_931.0, "ebitda": None, "cash": None, "document_id": None, "cadence_months": None},
        {
            "period": "HY2026", "revenue": 354_813.0, "ebitda": None, "cash": None,
            "document_id": row.document_id, "cadence_months": None,
        },
    ]


@pytest.mark.anyio
async def test_revenue_trend_prefers_month_end_label_over_hy_label(async_client, async_session):
    # "HY2026" alone doesn't say which calendar month the period ends --
    # the deterministically-extracted month/year label is clearer on an
    # axis and should win over the bare "HY" label when both exist.
    row = await _add_metrics_row(
        async_session,
        revenue=100_000.0,
        extracted_at=datetime(2026, 7, 6),
        fm_reporting_period="HY2026",
        fm_reporting_period_end="Dec 2025",
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [{
        "period": "Dec 2025", "revenue": 100_000.0, "ebitda": None, "cash": None,
        "document_id": row.document_id, "cadence_months": None,
    }]


@pytest.mark.anyio
async def test_revenue_trend_includes_ebitda_and_cash(async_client, async_session):
    row = await _add_metrics_row(async_session, revenue=100_000.0, ebitda=-20_000.0, cash=50_000.0)

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    points = response.json()
    assert points == [{
        "period": points[0]["period"], "revenue": 100_000.0, "ebitda": -20_000.0, "cash": 50_000.0,
        "document_id": row.document_id, "cadence_months": None,
    }]


@pytest.mark.anyio
async def test_revenue_trend_prepended_prior_point_includes_ebitda_and_cash(async_client, async_session):
    row = await _add_metrics_row(
        async_session,
        revenue=354_813.0,
        revenue_prior=340_931.0,
        ebitda=-473_739.0,
        ebitda_prior=-395_561.0,
        cash=735_189.0,
        cash_prior=72_382.0,
        fm_reporting_period_end="Dec 2025",
        fm_reporting_period_end_prior="Dec 2024",
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    assert response.json() == [
        {
            "period": "Dec 2024", "revenue": 340_931.0, "ebitda": -395_561.0, "cash": 72_382.0,
            "document_id": None, "cadence_months": None,
        },
        {
            "period": "Dec 2025", "revenue": 354_813.0, "ebitda": -473_739.0, "cash": 735_189.0,
            "document_id": row.document_id, "cadence_months": None,
        },
    ]


@pytest.mark.anyio
async def test_revenue_trend_does_not_prepend_prior_point_with_two_real_documents(async_client, async_session):
    # Once a second document is uploaded, that's a real second row -- the
    # embedded prior comparative on the first document must not also be
    # injected, which would double-count / fabricate a third point.
    base = datetime(2025, 1, 1)
    await _add_metrics_row(
        async_session, revenue=100_000.0, revenue_prior=90_000.0, extracted_at=base
    )
    await _add_metrics_row(
        async_session, revenue=200_000.0, extracted_at=base + timedelta(days=180)
    )

    response = await async_client.get("/metrics/dashboard/revenue-trend")

    assert response.status_code == 200
    assert len(response.json()) == 2
