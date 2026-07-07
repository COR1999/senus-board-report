"""
Tests for the lightweight column-migration helper in app/core/database.py.

There's no Alembic in this project, and `Base.metadata.create_all` only
creates missing *tables* -- it never alters an existing table's columns.
`_add_missing_columns` is the safe, idempotent alternative for a table
that already existed in production before new nullable columns were added
to its model (financial_metrics, live on Railway since feature/kpi-system).
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, _add_missing_columns
import app.models  # noqa: F401 -- registers all models on Base.metadata


@pytest.mark.anyio
async def test_add_missing_columns_adds_them_to_an_old_shape_table():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    async with engine.begin() as conn:
        # Simulate the real production scenario: a `financial_metrics`
        # table that already exists, created before the *_prior columns
        # existed on the model -- deliberately NOT using Base.metadata,
        # since create_all would just create the current (already-updated)
        # shape and never exercise this code path.
        await conn.execute(text(
            "CREATE TABLE financial_metrics ("
            "id INTEGER PRIMARY KEY, document_id INTEGER, revenue FLOAT"
            ")"
        ))
        await _add_missing_columns(conn)

        def get_columns(sync_conn):
            from sqlalchemy import inspect
            return {c["name"] for c in inspect(sync_conn).get_columns("financial_metrics")}

        columns = await conn.run_sync(get_columns)

    assert "revenue_prior" in columns
    assert "cash_prior" in columns
    assert "ebitda_prior" in columns
    assert "gross_margin_prior" in columns
    assert "operating_margin_prior" in columns
    # Original columns must survive untouched.
    assert "revenue" in columns
    assert "document_id" in columns

    await engine.dispose()


@pytest.mark.anyio
async def test_add_missing_columns_is_idempotent():
    """Running it twice (e.g. two app restarts) must not error."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE financial_metrics ("
            "id INTEGER PRIMARY KEY, document_id INTEGER, revenue FLOAT"
            ")"
        ))
        await _add_missing_columns(conn)
        await _add_missing_columns(conn)  # must not raise "column already exists"

    await engine.dispose()


@pytest.mark.anyio
async def test_add_missing_columns_adds_content_hash_to_an_old_shape_documents_table():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE documents (id INTEGER PRIMARY KEY, filename VARCHAR)"
        ))
        await _add_missing_columns(conn)

        def get_columns(sync_conn):
            from sqlalchemy import inspect
            return {c["name"] for c in inspect(sync_conn).get_columns("documents")}

        columns = await conn.run_sync(get_columns)

    assert "content_hash" in columns
    assert "filename" in columns

    await engine.dispose()


@pytest.mark.anyio
async def test_add_missing_columns_skips_a_table_that_does_not_exist_yet():
    """A tracked table (e.g. `documents`) that hasn't been created at all in
    this database yet must be skipped, not raise -- `Base.metadata.create_all`
    (which always runs first in the real app) is what creates it, with every
    current column already present."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    async with engine.begin() as conn:
        # Only financial_metrics exists -- documents does not.
        await conn.execute(text(
            "CREATE TABLE financial_metrics ("
            "id INTEGER PRIMARY KEY, document_id INTEGER, revenue FLOAT"
            ")"
        ))
        await _add_missing_columns(conn)  # must not raise NoSuchTableError

    await engine.dispose()


@pytest.mark.anyio
async def test_add_missing_columns_noop_on_already_current_table():
    """A table created via the current model (create_all) already has
    every column -- the helper must find nothing to add."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)  # should be a clean no-op

    await engine.dispose()
