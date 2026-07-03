"""
Database initialization and session management.
Uses SQLAlchemy 2.0 async patterns.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
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