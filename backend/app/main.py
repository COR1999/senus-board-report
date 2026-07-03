"""
FastAPI application factory and initialization.
"""

from dotenv import load_dotenv 
load_dotenv()

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.api.routes import documents, reports, metrics


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("🚀 Starting Senus Board Intelligence Platform")
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down application")
    try:
        await close_db()
        logger.info("✅ Database connection closed")
    except Exception as e:
        logger.warning(f"⚠️  Error closing database: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered financial document analysis platform with Gemini AI integration",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(documents.router, tags=["documents"])
    app.include_router(reports.router, tags=["reports"])
    app.include_router(metrics.router, tags=["metrics"])

    # Health check endpoint
    @app.get("/health", tags=["system"])
    async def health_check() -> Dict[str, Any]:
        """
        Check application health status.
        
        Returns:
            - status: Application status (healthy/degraded)
            - version: Application version
            - database: Database connection status
            - gemini_available: Gemini API availability
        """
        from app.services.gemini_service import GeminiAnalysisService
        
        service = GeminiAnalysisService()
        
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "database": "connected",
            "gemini_available": service.is_available(),
            "environment": "development" if settings.DEBUG else "production"
        }

    # Root endpoint
    @app.get("/", tags=["system"])
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "description": "Financial document analysis platform with AI",
            "docs": "/docs",
            "health": "/health"
        }

    # Custom OpenAPI schema
    def custom_openapi() -> Dict[str, Any]:
        """Generate custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title="Senus Board Intelligence API",
            version=settings.APP_VERSION,
            description="API for financial document analysis with Google Gemini AI integration",
            routes=app.routes,
        )
        
        # Add custom info
        openapi_schema["info"]["x-logo"] = {
            "url": "https://senus-board.vercel.app/logo.png",
            "altText": "Senus Board Logo"
        }
        
        # Add dynamic server info based on environment
        if settings.DEBUG:
            openapi_schema["servers"] = [
                {"url": "http://127.0.0.1:8000", "description": "Development"},
            ]
        else:
            openapi_schema["servers"] = [
                {"url": "https://your-railway-url.up.railway.app", "description": "Production"},
            ]
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    logger.info(f"✅ FastAPI application created: {settings.APP_NAME} v{settings.APP_VERSION}")
    return app


# Create and export app instance
app = create_app()


# Exception handlers (optional but recommended)
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "detail": "An unexpected error occurred",
        "error": str(exc) if settings.DEBUG else "Internal server error"
    }