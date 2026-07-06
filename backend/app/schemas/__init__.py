"""Schemas package."""

from app.schemas.financial import (
    # Financial Metrics
    FinancialMetricsBase,
    FinancialMetricsCreate,
    FinancialMetricsResponse,
    # Revenue Trend
    RevenueTrendPoint,
    # Document
    DocumentBase,
    DocumentCreate,
    DocumentResponse,
    DocumentWithText,
)
from app.schemas.report import (
    ReportMetricsSummary,
    ReportSummary,
    ReportResponse,
    ReportDeleteResponse,
    DashboardDocument,
    ReportDashboardResponse,
)

__all__ = [
    "FinancialMetricsBase",
    "FinancialMetricsCreate",
    "FinancialMetricsResponse",
    "RevenueTrendPoint",
    "DocumentBase",
    "DocumentCreate",
    "DocumentResponse",
    "DocumentWithText",
    "ReportMetricsSummary",
    "ReportSummary",
    "ReportResponse",
    "ReportDeleteResponse",
    "DashboardDocument",
    "ReportDashboardResponse",
]