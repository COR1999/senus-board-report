"""Database session and connection management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, NullPool
from typing import Any, Generator, AsyncGenerator
from app.core.config import get_settings

settings: Any = get_settings()

# Get database URL
DATABASE_URL = settings.DATABASE_URL

# ============ SYNCHRONOUS ENGINE (for non-async routes) ============
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"),
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"),
        future=True,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

def get_db() -> Generator[Session, None, None]:
    """Dependency to get synchronous database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============ ASYNCHRONOUS ENGINE (for async routes) ============
# Convert DATABASE_URL to async format if needed
ASYNC_DATABASE_URL = DATABASE_URL
if "postgresql://" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif "sqlite:///" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
elif "sqlite://" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite:///:memory:")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    poolclass=NullPool if "sqlite" in ASYNC_DATABASE_URL else None,
)

async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get asynchronous database session."""
    async with async_session_maker() as session:
        yield session