"""
Tests for PDFExtractionService.render_page_images -- the page-image
rendering used as input to a Gemini vision extraction call for a scanned
PDF with no text layer at all (see report_service._generate's
`vision_extracted` branch) -- and has_extractable_text, which decides
whether that branch should fire at all.
"""
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
    # with, which is exactly why the vision path exists at all.
    extracted_text = PDFExtractionService.extract_text(str(FIXTURE))
    assert PDFExtractionService.has_extractable_text(extracted_text) is False


def test_render_page_images_raises_for_a_missing_file():
    with pytest.raises(FileNotFoundError):
        PDFExtractionService.render_page_images("does/not/exist.pdf")


class TestHasExtractableText:
    """
    A real bug, found by actually running the vision path against the real
    ADF fixture end-to-end (not caught by any mocked test, which all set
    extracted_text="" directly): extract_text() prepends a "--- Page N ---"
    marker for *every* page regardless of whether that page had real text,
    so a fully scanned document's extracted_text is never a truly empty
    string -- a naive `bool(text.strip())` reports "has text" anyway.
    """

    def test_empty_string_has_no_text(self):
        assert PDFExtractionService.has_extractable_text("") is False

    def test_whitespace_only_has_no_text(self):
        assert PDFExtractionService.has_extractable_text("   \n\n  ") is False

    def test_page_markers_alone_have_no_real_text(self):
        markers_only = "--- Page 1 ---\n\n--- Page 2 ---\n\n--- Page 3 ---\n"
        assert PDFExtractionService.has_extractable_text(markers_only) is False

    def test_real_content_alongside_markers_is_detected(self):
        with_content = "--- Page 1 ---\nRevenue: 100,000\n--- Page 2 ---\n"
        assert PDFExtractionService.has_extractable_text(with_content) is True
