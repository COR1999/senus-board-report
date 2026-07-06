"""
Database initialization and session management.
Uses SQLAlchemy 2.0 async patterns.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Global engine and session factory
_engine = None
_async_session_maker = None

# (table, [(column_name, sql_type), ...]) for columns added to an
# ALREADY-EXISTING table after its initial release. `Base.metadata.create_all`
# only creates missing *tables* -- it never alters an existing table's
# columns, so a table that already exists in production (financial_metrics,
# live on Railway since feature/kpi-system) needs this instead. There's no
# Alembic in this project, so this is a small, targeted, idempotent
# alternative: check via the inspector whether each column already exists
# before adding it, rather than relying on non-portable `IF NOT EXISTS`
# column syntax. Safe to run every startup.
_COLUMNS_ADDED_AFTER_INITIAL_RELEASE = {
    "financial_metrics": [
        ("revenue_prior", "FLOAT"),
        ("cash_prior", "FLOAT"),
        ("ebitda_prior", "FLOAT"),
        ("gross_margin_prior", "FLOAT"),
        ("operating_margin_prior", "FLOAT"),
    ],
}


async def _add_missing_columns(conn: AsyncConnection) -> None:
    def get_existing_columns(sync_conn, table_name: str) -> set[str]:
        return {col["name"] for col in inspect(sync_conn).get_columns(table_name)}

    for table_name, columns in _COLUMNS_ADDED_AFTER_INITIAL_RELEASE.items():
        existing = await conn.run_sync(get_existing_columns, table_name)
        for column_name, sql_type in columns:
            if column_name not in existing:
                logger.info(f"Adding missing column {table_name}.{column_name}")
                await conn.execute(
                    text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}')
                )


async def init_db():
    """Initialize database engine and create tables."""
    global _engine, _async_session_maker
    
    settings = get_settings()
    
    # Convert postgresql:// to postgresql+asyncpg:// for async support
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    logger.info("Initializing database...")
    
    # Create async engine with production pooling
    _engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,      # Test connections before using
        pool_size=5,              # Number of persistent connections
        max_overflow=10,          # Extra connections if pool is full
    )
    
    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    
    # Create all tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)

    logger.info("✅ Database initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with _async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db():
    """Close database connection."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("✅ Database connection closed")