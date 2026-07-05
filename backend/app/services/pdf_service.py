"""PDF extraction service using PyMuPDF."""
import fitz  # PyMuPDF
from pathlib import Path
import os
from typing import Tuple


class PDFExtractionService:
    """Service for extracting text from PDF files."""
    
    UPLOAD_DIR = Path("uploads")
    
    @classmethod
    def ensure_upload_dir(cls) -> None:
        """Create uploads directory if it doesn't exist."""
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def save_pdf(cls, file_content: bytes, filename: str) -> str:
        """Save PDF file and return file path."""
        cls.ensure_upload_dir()
        filename = Path(filename).name
        file_path = cls.UPLOAD_DIR / filename
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return str(file_path)
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """Extract all text from PDF file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        try:
            pdf_document = fitz.open(file_path)
            extracted_text: str = ""
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                page_text = page.get_text()
                
                if isinstance(page_text, str):
                    extracted_text += f"\n--- Page {page_num + 1} ---\n"
                    extracted_text += page_text
                else:
                    extracted_text += f"\n--- Page {page_num + 1} ---\n"
                    extracted_text += str(page_text)
            
            pdf_document.close()
            return extracted_text.strip()
        
        except Exception as e:
            raise Exception(f"Error extracting PDF text: {str(e)}")
    
    @classmethod
    def extract_text_from_upload(cls, file_content: bytes, filename: str) -> Tuple[str, str]:
        """Upload PDF and extract text. Returns (file_path, extracted_text)."""
        file_path = cls.save_pdf(file_content, filename)
        extracted_text = cls.extract_text(file_path)
        return file_path, extracted_text