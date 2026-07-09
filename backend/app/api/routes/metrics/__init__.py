"""
Financial metrics endpoints.

Metrics are always written internally by report generation (see
ReportService._save_metrics) -- this router only reads them back for the
dashboard. There is no client-facing metrics CRUD.

Split by concern (each was previously a section of one ~800-line file):
- `_shared.py` -- constants and period/cadence helpers common to all three.
- `dashboard_summary.py` -- GET /dashboard/periods, GET /dashboard/summary.
- `charts.py` -- GET /dashboard/cost-waterfall, GET /dashboard/revenue-trend.
- `historical_insight.py` -- GET/PUT /dashboard/historical-insight.

`_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD` and `get_dashboard_periods` are
re-exported below because other modules import them directly:
`period_merge_service.py` reuses the same dashboard-eligibility filter, and
`test_period_merge.py` calls the periods endpoint as a plain function.
"""
from fastapi import APIRouter

from . import charts, dashboard_summary, historical_insight
from ._shared import _IS_CONFIDENT_ENOUGH_FOR_DASHBOARD  # noqa: F401 (re-exported for period_merge_service.py)
from .dashboard_summary import get_dashboard_periods  # noqa: F401 (re-exported for test_period_merge.py)

router = APIRouter(prefix="/metrics", tags=["metrics"])
router.include_router(dashboard_summary.router)
router.include_router(charts.router)
router.include_router(historical_insight.router)

__all__ = ["router", "_IS_CONFIDENT_ENOUGH_FOR_DASHBOARD", "get_dashboard_periods"]
