"""Tests for GET /metrics/dashboard/summary, particularly the sparkline `history` field."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.models.report import Report


async def _add_metrics_row(
    session: AsyncSession,
    *,
    revenue=None,
    customers=None,
    cash=None,
    ebitda=None,
    revenue_prior=None,
    cash_prior=None,
    ebitda_prior=None,
    bookings_value=None,
    extracted_at=None,
    fm_reporting_period=None,
    fm_reporting_period_prior=None,
    ai_reporting_period=None,
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
        revenue_prior=revenue_prior,
        cash_prior=cash_prior,
        ebitda_prior=ebitda_prior,
        bookings_value=bookings_value,
        reporting_period=fm_reporting_period,
        reporting_period_prior=fm_reporting_period_prior,
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(metrics)

    if ai_reporting_period is not None:
        session.add(Report(document_id=doc.id, summary={"reporting_period": ai_reporting_period}, status="completed"))

    await session.flush()  # flush (not commit) -- async_client shares this session, and
    # conftest.py's async_session fixture rolls back at teardown for test isolation.
    return metrics


async def _add_balance_sheet_row(session: AsyncSession, document_id: int, **fields) -> BalanceSheetMetrics:
    bs = BalanceSheetMetrics(document_id=document_id, extracted_at=datetime.utcnow(), **fields)
    session.add(bs)
    await session.flush()
    return bs


@pytest.mark.anyio
async def test_dashboard_summary_zero_rows(async_client, async_session):
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    for key in ("revenue", "customers", "cash", "ebitda"):
        assert body[key]["history"] == []
        assert body[key]["trend"] == "neutral"
        assert body[key]["change"] == 0
    assert body["current_period"] is None
    assert body["prior_period"] is None


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


@pytest.mark.anyio
async def test_dashboard_summary_ratio_kpis_are_na_with_no_data(async_client, async_session):
    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    for key in ("ebitda_margin", "cash_runway", "interest_cover", "roce"):
        assert body[key]["value"] == "N/A"
        assert body[key]["trend"] == "neutral"
        assert body[key]["history"] == []


@pytest.mark.anyio
async def test_dashboard_summary_single_row_uses_embedded_prior_for_change(async_client, async_session):
    """
    With only one FinancialMetrics row (the realistic case today -- one
    filing ever uploaded), change/trend must come from that row's own
    embedded prior-period comparative, not always read 0%/neutral.
    """
    await _add_metrics_row(
        async_session,
        revenue=354_813.0, revenue_prior=340_931.0,
        cash=735_189.0, cash_prior=72_382.0,
        ebitda=-473_739.0, ebitda_prior=-395_561.0,
        customers=138,
    )

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()

    assert body["revenue"]["change"] == 4.1
    assert body["revenue"]["trend"] == "up"
    assert body["revenue"]["history"] == [340_931.0, 354_813.0]

    # A bigger loss (-473,739 vs -395,561) must read as "down", not "up" --
    # regression guard for the negative-base calculate_change bug.
    assert body["ebitda"]["change"] < 0
    assert body["ebitda"]["trend"] == "down"
    assert body["ebitda"]["value"] == "-€474K"

    # customers has no _prior column -- single point, no fallback possible.
    assert body["customers"]["history"] == [138.0]
    assert body["customers"]["trend"] == "neutral"


@pytest.mark.anyio
async def test_dashboard_summary_computes_ratio_kpis_from_balance_sheet_metrics(async_client, async_session):
    metrics = await _add_metrics_row(
        async_session,
        revenue=354_813.0, revenue_prior=340_931.0,
        cash=735_189.0, cash_prior=72_382.0,
        ebitda=-473_739.0, ebitda_prior=-395_561.0,
        customers=138,
    )
    await _add_balance_sheet_row(
        async_session,
        metrics.document_id,
        interest_expense=1_391.0, interest_expense_prior=1_036.0,
        operating_result=-483_753.0, operating_result_prior=-405_577.0,
        capital_employed=637_554.0, capital_employed_prior=258_784.0,
        net_cash_used_operating=410_291.0, net_cash_used_operating_prior=450_181.0,
    )

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()

    # ebitda_margin = -473,739 / 354,813 * 100
    assert round(body["ebitda_margin"]["history"][-1], 1) == -133.5
    # A worsening margin must trend down.
    assert body["ebitda_margin"]["trend"] == "down"

    # cash_runway ~= 735,189 / (410,291/6) ~= 10.8 months
    assert body["cash_runway"]["value"] == "10.8 mo"

    # roce improved from -156.7% to -75.9% -- must trend up despite both
    # being negative (regression guard, same bug class as ebitda above).
    assert body["roce"]["trend"] == "up"

    # interest_cover = ebitda / interest_expense (a DSCR proxy)
    assert body["interest_cover"]["value"] == "-340.6x"


@pytest.mark.anyio
async def test_dashboard_summary_cash_runway_shows_cash_flow_positive_not_na(async_client, async_session):
    """Operations that aren't burning cash shouldn't show a nonsensical
    "runway" -- but should read differently from genuinely missing data."""
    metrics = await _add_metrics_row(async_session, revenue=100_000.0, cash=50_000.0)
    await _add_balance_sheet_row(
        async_session,
        metrics.document_id,
        net_cash_used_operating=-20_000.0,  # negative = cash-flow positive
    )

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    assert response.json()["cash_runway"]["value"] == "Cash flow +"


@pytest.mark.anyio
async def test_dashboard_summary_bookings_is_na_when_not_extracted(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0)

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()["bookings"]
    assert body["value"] == "N/A"
    assert body["trend"] == "neutral"
    assert body["change"] == 0


@pytest.mark.anyio
async def test_dashboard_summary_bookings_shows_formatted_value(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0, bookings_value=700_000.0)

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()["bookings"]
    assert body["value"] == "€700K"
    # No prior-period comparative exists for bookings -- always neutral,
    # never a fabricated delta.
    assert body["trend"] == "neutral"
    assert body["change"] == 0


@pytest.mark.anyio
async def test_dashboard_summary_falls_back_to_ai_reporting_period_and_derives_prior(async_client, async_session):
    # No deterministic FinancialMetrics.reporting_period set -- falls back
    # to the AI-extracted Report.summary field, then derives a best-effort
    # prior label since no explicit prior label exists in this fallback.
    await _add_metrics_row(async_session, revenue=100_000.0, ai_reporting_period="H1 2025")

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["current_period"] == "H1 2025"
    assert body["prior_period"] == "H1 2024"


@pytest.mark.anyio
async def test_dashboard_summary_prefers_deterministic_period_over_ai_fallback(async_client, async_session):
    # FinancialMetrics.reporting_period/_prior (deterministic, e.g.
    # "HY2026"/"HY25") must win over the AI-extracted Report.summary value
    # even when both exist -- the deterministic extractor is the reliable
    # source; the AI path is a fallback for when it can't find anything.
    await _add_metrics_row(
        async_session,
        revenue=100_000.0,
        fm_reporting_period="HY2026",
        fm_reporting_period_prior="HY25",
        ai_reporting_period="H1 2025",
    )

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["current_period"] == "HY2026"
    assert body["prior_period"] == "HY25"


@pytest.mark.anyio
async def test_dashboard_summary_period_is_none_without_a_report(async_client, async_session):
    await _add_metrics_row(async_session, revenue=100_000.0)

    response = await async_client.get("/metrics/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["current_period"] is None
    assert body["prior_period"] is None
