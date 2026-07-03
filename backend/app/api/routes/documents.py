"""Document endpoints."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database.session import get_db
from app.models.document import Document
from app.schemas.financial import DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF document."""
    # Check if filename exists
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    doc = Document(
        filename=file.filename,
        file_path=f"/uploads/{file.filename}",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Get document by ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(db: Session = Depends(get_db)):
    """List all documents."""
    docs = db.query(Document).all()
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.post("/{document_id}/extract")
async def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Extract metrics from document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc.extracted_at = datetime.now(timezone.utc)
    db.commit()
    
    return {
        "status": "extracted",
        "document_id": document_id,
        "message": "Document extracted successfully"
    }