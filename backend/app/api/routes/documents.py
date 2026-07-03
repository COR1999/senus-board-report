"""Document endpoints."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database.session import get_db
from app.models.document import Document
from app.schemas.financial import DocumentResponse, DocumentWithText
from app.services.pdf_service import PDFExtractionService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF document and extract text."""
    # Validate file
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Extract text from PDF
        file_path, extracted_text = PDFExtractionService.extract_text_from_upload(
            file_content, 
            file.filename
        )
        
        # Create document record
        doc = Document(
            filename=file.filename,
            file_path=file_path,
            extracted_text=extracted_text,
            extracted_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        return DocumentResponse.model_validate(doc)
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.get("/{document_id}", response_model=DocumentWithText)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Get document by ID with extracted text."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentWithText.model_validate(doc)


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
    
    if not doc.extracted_text:
        raise HTTPException(status_code=400, detail="No text extracted from document")
    
    return {
        "status": "extracted",
        "document_id": document_id,
        "text_length": len(doc.extracted_text),
        "message": "Document text extracted successfully"
    }