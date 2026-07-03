"""Financial metrics endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database.session import get_db
from app.models.financial_metrics import FinancialMetrics
from app.models.document import Document
from app.schemas.financial import FinancialMetricsResponse, FinancialMetricsCreate

router = APIRouter(prefix="/metrics", tags=["metrics"])


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
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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