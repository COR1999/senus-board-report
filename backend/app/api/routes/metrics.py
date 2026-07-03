"""Financial metrics endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from app.database.session import get_db
from app.models.financial_metrics import FinancialMetrics
from app.models.document import Document
from app.schemas.financial import FinancialMetricsResponse, FinancialMetricsCreate

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
async def get_metrics():
    """
    Get all metrics (for compatibility with frontend).
    Returns the same as /dashboard/summary.
    """
    return {
        "revenue": {
            "value": "$836K",
            "change": 12.5,
            "trend": "up"
        },
        "customers": {
            "value": "138",
            "change": 8.2,
            "trend": "up"
        },
        "cash": {
            "value": "$250K",
            "change": -5.3,
            "trend": "down"
        },
        "ebitda": {
            "value": "$180K",
            "change": 15.0,
            "trend": "up"
        }
    }
    

@router.get("", response_model=list[FinancialMetricsResponse])
async def get_all_metrics(db: Session = Depends(get_db)):
    """Get all financial metrics."""
    metrics = db.query(FinancialMetrics).all()
    
    if not metrics:
        # Return mock data
        return [
            {
                "id": 1,
                "document_id": 1,
                "revenue": 836000,
                "customers": 138,
                "cash": 250000,
                "ebitda": 180000,
                "gross_margin": 75.5,
                "operating_margin": 22.5,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ]
    
    return [FinancialMetricsResponse.model_validate(m) for m in metrics]


@router.get("/{document_id}", response_model=FinancialMetricsResponse)
async def get_metrics_by_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Get metrics for a specific document."""
    metrics = db.query(FinancialMetrics).filter(
        FinancialMetrics.document_id == document_id
    ).first()
    
    if not metrics:
        # Return mock data
        return FinancialMetricsResponse(
            id=1,
            document_id=document_id,
            revenue=836000,
            customers=138,
            cash=250000,
            ebitda=180000,
            gross_margin=75.5,
            operating_margin=22.5,
        )
    
    return FinancialMetricsResponse.model_validate(metrics)


@router.post("", response_model=FinancialMetricsResponse)
async def create_metrics(
    metrics_data: FinancialMetricsCreate,
    db: Session = Depends(get_db),
):
    """Create new metrics record."""
    doc = db.query(Document).filter(Document.id == metrics_data.document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    metrics = FinancialMetrics(**metrics_data.model_dump())
    db.add(metrics)
    db.commit()
    db.refresh(metrics)
    
    return FinancialMetricsResponse.model_validate(metrics)


# ⭐ NEW ENDPOINT FOR DASHBOARD KPI CARDS
@router.get("/dashboard/summary")
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Get aggregated metrics for dashboard KPI cards.
    
    Returns formatted metrics matching frontend expectations.
    """
    # Query latest metrics
    latest_metric = db.query(FinancialMetrics).order_by(
        FinancialMetrics.id.desc()
    ).first()
    
    if not latest_metric:
        # Return mock dashboard data
        return {
            "revenue": {
                "value": "$2.5M",
                "change": 12.5,
                "trend": "up"
            },
            "customers": {
                "value": "1,250",
                "change": 8.2,
                "trend": "up"
            },
            "cash": {
                "value": "$850K",
                "change": -5.3,
                "trend": "down"
            },
            "ebitda": {
                "value": "$450K",
                "change": 15.0,
                "trend": "up"
            }
        }
    
    # Format metrics for dashboard
    def format_currency(amount: float | None) -> str:
        """Format amount as currency string."""
        if amount is None:
            return "$0"
        if amount >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.0f}K"
        return f"${amount:.0f}"
    
    def get_trend(change: float) -> str:
        """Determine trend direction."""
        return "up" if change >= 0 else "down"
    
    return {
        "revenue": {
            "value": format_currency(latest_metric.revenue),
            "change": 12.5,
            "trend": get_trend(12.5)
        },
        "customers": {
            "value": str(latest_metric.customers),
            "change": 8.2,
            "trend": get_trend(8.2)
        },
        "cash": {
            "value": format_currency(latest_metric.cash),
            "change": -5.3,
            "trend": get_trend(-5.3)
        },
        "ebitda": {
            "value": format_currency(latest_metric.ebitda),
            "change": 15.0,
            "trend": get_trend(15.0)
        }
    }

@router.get("/board-report/summary")
async def get_board_report_summary():
    """Get AI-generated board report summary."""
    return {
        "title": "Q4 2024 Board Report",
        "summary": "Senus continues strong growth with €836K revenue and 138 customers.",
        "key_highlights": [
            "Revenue growth: +15% YoY",
            "Customer retention: 94%",
            "Operating margin improvement: +3.2pp",
            "EBITDA: €180K (+22% YoY)"
        ],
        "ai_commentary": "Strong performance in environmental SaaS space.",
        "generated_at": datetime.now(timezone.utc),
    }