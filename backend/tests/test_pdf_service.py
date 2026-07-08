"""
Tests for PDFExtractionService.render_page_images -- the page-image
rendering used as input to a Gemini vision extraction call for a scanned
PDF with no text layer at all (see report_service._generate's
`vision_extracted` branch).
"""
import re
from pathlib import Path

import pytest

from app.services.pdf_service import PDFExtractionService

FIXTURE = Path(__file__).parent / "fixtures" / "ADF_Farm_Solutions_Financial_Statements_Jun2025.pdf"


def test_render_page_images_returns_one_jpeg_per_page():
    images = PDFExtractionService.render_page_images(str(FIXTURE))

    # The real fixture is a 23-page scanned document -- confirmed directly
    # via PyMuPDF while diagnosing this document's lack of a text layer.
    assert len(images) == 23
    for image in images:
        assert isinstance(image, bytes)
        assert image.startswith(b"\xff\xd8")  # JPEG magic bytes


def test_render_page_images_confirms_the_source_has_no_extractable_text():
    # Cross-check against the other half of this document's real shape --
    # it genuinely has nothing for the deterministic text pipeline to work
    # with, which is exactly why the vision path exists at all. extract_text
    # always prepends a "--- Page N ---" marker per page regardless of
    # content, so strip those out before checking for real extracted text.
    extracted_text = PDFExtractionService.extract_text(str(FIXTURE))
    without_markers = re.sub(r"---\s*Page\s*\d+\s*---", "", extracted_text)
    assert without_markers.strip() == ""


def test_render_page_images_raises_for_a_missing_file():
    with pytest.raises(FileNotFoundError):
        PDFExtractionService.render_page_images("does/not/exist.pdf")
