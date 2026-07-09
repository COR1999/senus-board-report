"""PDF extraction service using PyMuPDF."""
import fitz  # PyMuPDF
from pathlib import Path
import os
import re
from typing import List, Tuple

# Matches extract_text()'s own "--- Page N ---" markers, prepended for
# *every* page regardless of whether that page had any real text -- so a
# fully scanned PDF's extracted_text is never a truly empty string, just
# these markers with nothing real between them. Shared here (not duplicated
# ad hoc by callers) so "does this document have real text" is answered the
# same way everywhere it matters.
_PAGE_MARKER_RE = re.compile(r"---\s*Page\s*\d+\s*---")


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
        
        pdf_document = None
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

            return extracted_text.strip()

        except Exception as e:
            raise Exception(f"Error extracting PDF text: {str(e)}")
        finally:
            # Without this, an exception raised while iterating pages (e.g.
            # a malformed page) would skip the close() call this try block
            # used to only reach on the success path, leaking the file
            # handle -- render_page_images() below already gets this right.
            if pdf_document is not None:
                pdf_document.close()
    
    @classmethod
    def has_extractable_text(cls, extracted_text: str) -> bool:
        """
        True if `extracted_text` (as returned by extract_text()) contains
        any real content beyond the page markers extract_text() always
        prepends. A naive `bool(extracted_text.strip())` is NOT enough for
        this -- confirmed as a real bug, not hypothetical: for a fully
        scanned PDF (e.g. ADF Farm Solutions' statements, every page a
        single embedded image with zero real text), extract_text() still
        returns a non-empty string of nothing but "--- Page N ---" markers,
        so `.strip()` alone reports it as "has text" and a scanned document
        silently took the wrong (deterministic-text) extraction path
        instead of the Gemini vision one meant for exactly this case.
        """
        return bool(_PAGE_MARKER_RE.sub("", extracted_text).strip())

    @classmethod
    def extract_text_from_upload(cls, file_content: bytes, filename: str) -> Tuple[str, str]:
        """Upload PDF and extract text. Returns (file_path, extracted_text)."""
        file_path = cls.save_pdf(file_content, filename)
        extracted_text = cls.extract_text(file_path)
        return file_path, extracted_text

    @classmethod
    def render_page_images(cls, file_path: str, dpi: int = 150) -> List[bytes]:
        """
        Renders every page of a PDF to JPEG bytes -- used as input to a
        Gemini vision extraction call when `extract_text()` found no text
        layer at all (a scanned document, e.g. ADF Farm Solutions'
        statements: confirmed via PyMuPDF that every page is a single
        embedded JPEG image with zero extractable text). Renders via
        `get_pixmap()` rather than extracting the embedded image directly,
        so this works the same way regardless of how a given PDF happens to
        have embedded its scanned pages. 150 DPI balances legibility for a
        vision model against request size for a many-page document.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        pdf_document = fitz.open(file_path)
        try:
            return [page.get_pixmap(dpi=dpi).tobytes("jpeg") for page in pdf_document]
        finally:
            pdf_document.close()