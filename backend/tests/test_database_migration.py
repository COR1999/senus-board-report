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


class TestNullableColumnBackfill:
    """
    A real production bug, not hypothetical: importing ADF Farm Solutions
    (a document that genuinely doesn't disclose a customer count) was the
    first insert to ever attempt a NULL `customers` value, and hit Postgres'
    NotNullViolationError -- the SQLAlchemy model had said Optional[int] for
    a long time, but `Base.metadata.create_all` never alters an existing
    table's column constraints, so the live column was still NOT NULL from
    whenever the table was first created.
    """

    @pytest.mark.anyio
    async def test_skipped_entirely_on_sqlite_no_error(self):
        # ALTER COLUMN ... DROP NOT NULL is Postgres-only syntax -- running
        # against a SQLite connection (every test/local run) must not even
        # attempt it, let alone error.
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _add_missing_columns(conn)  # must not raise
        await engine.dispose()

    @pytest.mark.anyio
    async def test_drops_not_null_on_every_original_baseline_column_for_postgres(self):
        # A minimal fake standing in for AsyncConnection -- real Postgres
        # isn't available in this test environment, so this verifies the
        # *logic* (which table, which columns, right SQL shape) rather than
        # actually executing against a live database.
        executed_sql: list[str] = []

        class _FakeDialect:
            name = "postgresql"

        class _FakeConn:
            dialect = _FakeDialect()

            async def run_sync(self, fn, *args):
                # _add_missing_columns calls run_sync with two different
                # sync helpers (table_exists, get_existing_columns) --
                # dispatch on name since both are nested closures.
                if fn.__name__ == "table_exists":
                    return True  # matches production: the table exists
                if fn.__name__ == "get_existing_columns":
                    return set()  # irrelevant to this test, must be iterable
                raise AssertionError(f"unexpected run_sync target: {fn.__name__}")

            async def execute(self, clause):
                executed_sql.append(str(clause))

        await _add_missing_columns(_FakeConn())

        for column in ("revenue", "customers", "cash", "ebitda", "gross_margin", "operating_margin"):
            assert any(
                f"ALTER TABLE financial_metrics ALTER COLUMN {column} DROP NOT NULL" in sql
                for sql in executed_sql
            ), f"missing DROP NOT NULL for {column}"
