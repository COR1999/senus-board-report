"""Tests for GET/PUT /api/reports/{report_id}/insights (persisted AI Board Insights)."""
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.report import Report
from app.models.report_insights import ReportInsights


async def _add_report(session: AsyncSession) -> Report:
    doc = Document(filename="test.pdf", status="completed", created_at=datetime.utcnow())
    session.add(doc)
    await session.flush()

    report = Report(document_id=doc.id, status="completed")
    session.add(report)
    await session.flush()
    return report


@pytest.mark.anyio
async def test_get_insights_404s_when_none_have_ever_been_generated(async_client, async_session):
    report = await _add_report(async_session)

    response = await async_client.get(f"/api/reports/{report.id}/insights")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_insights_404s_for_a_nonexistent_report(async_client, async_session):
    response = await async_client.get("/api/reports/999999/insights")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_put_creates_insights_for_a_report_with_none_stored_yet(async_client, async_session):
    report = await _add_report(async_session)

    response = await async_client.put(
        f"/api/reports/{report.id}/insights",
        json={
            "insights": [
                {"text": "Revenue grew 21.6% YoY", "type": "positive", "action": "Keep it up", "category": "Growth & Revenue"},
            ],
            "model_version": "gemini-2.5-flash",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == report.id
    assert body["insights"] == [
        {"text": "Revenue grew 21.6% YoY", "type": "positive", "action": "Keep it up", "category": "Growth & Revenue"}
    ]
    assert body["model_version"] == "gemini-2.5-flash"


@pytest.mark.anyio
async def test_get_returns_what_was_previously_put(async_client, async_session):
    report = await _add_report(async_session)
    await async_client.put(
        f"/api/reports/{report.id}/insights",
        json={"insights": [{"text": "Cash position is strong", "type": "positive"}], "model_version": "gemini-2.5-flash"},
    )

    response = await async_client.get(f"/api/reports/{report.id}/insights")

    assert response.status_code == 200
    assert response.json()["insights"] == [
        {"text": "Cash position is strong", "type": "positive", "action": "", "category": None}
    ]


@pytest.mark.anyio
async def test_put_upserts_replacing_a_prior_stored_result_not_appending(async_client, async_session):
    report = await _add_report(async_session)
    await async_client.put(
        f"/api/reports/{report.id}/insights",
        json={"insights": [{"text": "Old insight", "type": "risk"}], "model_version": "gemini-2.5-flash"},
    )

    response = await async_client.put(
        f"/api/reports/{report.id}/insights",
        json={"insights": [{"text": "New insight", "type": "opportunity"}], "model_version": "gemini-2.5-flash"},
    )

    assert response.status_code == 200
    assert len(response.json()["insights"]) == 1
    assert response.json()["insights"][0]["text"] == "New insight"

    # A single row still exists in the database -- not a second one appended.
    from sqlalchemy import select

    result = await async_session.execute(select(ReportInsights).where(ReportInsights.report_id == report.id))
    assert len(result.scalars().all()) == 1


@pytest.mark.anyio
async def test_put_404s_for_a_nonexistent_report(async_client, async_session):
    response = await async_client.put(
        "/api/reports/999999/insights",
        json={"insights": [{"text": "x", "type": "positive"}], "model_version": "gemini-2.5-flash"},
    )

    assert response.status_code == 404
