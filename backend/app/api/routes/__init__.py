"""API routes package."""
from app.api.routes.documents import router as documents_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.reports import router as reports_router

__all__ = ["documents_router", "metrics_router", "reports_router"]