from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Create app first
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered board reporting dashboard",
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import database
from app.database.base import Base
from app.database.session import engine

# Import models IN THIS EXACT ORDER
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.report import Report

# Create tables
Base.metadata.create_all(bind=engine)

# Import routers
from app.api.routes import documents_router, metrics_router

app.include_router(documents_router)
app.include_router(metrics_router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Senus Board Report API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }