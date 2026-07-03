"""Database session and connection management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
from app.core.config import settings

# Get database URL
DATABASE_URL = settings.DATABASE_URL

# Create engine based on database type
if "sqlite" in DATABASE_URL:
    # SQLite for development
    engine = create_engine(
        DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"),
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        echo=(settings.ENVIRONMENT == "development"),
        future=True,
        pool_pre_ping=True,
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()