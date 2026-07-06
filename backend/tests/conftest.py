"""Pytest configuration and fixtures for async testing"""
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.pool import NullPool
import os

from app.core.database import Base, get_db
from app.main import app

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:"
)


# The Report model uses Postgres JSONB (the production database). SQLite
# has no native JSONB type, so teach it to compile JSONB columns as JSON
# when running the test suite against the default SQLite test database.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture(scope="session")
async def test_async_engine():
    """Create test database engine"""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def async_session(
    test_async_engine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create isolated database session for each test"""
    async_session_maker_test = async_sessionmaker(
        test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session_maker_test() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def async_client(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Setup test HTTP client with dependency override"""
    
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    app.dependency_overrides[get_db] = override_get_session
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test-server",
    ) as client:
        yield client
    
    # Cleanup
    app.dependency_overrides.clear()

# Configure pytest for async
pytest_plugins = ("pytest_asyncio",)