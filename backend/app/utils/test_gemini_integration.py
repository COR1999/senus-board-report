"""
Integration tests for Gemini service.
"""

import pytest
import asyncio
from app.services.gemini_service import GeminiAnalysisService


@pytest.mark.asyncio
async def test_extract_metrics_from_text():
    """Test financial metrics extraction."""
    service = GeminiAnalysisService()
    
    sample_text = """
    Annual Report 2024
    
    Revenue: €836K
    Customers: 138
    Cash: €250K
    EBITDA: €120K
    Gross Margin: 75%
    Operating Margin: 45%
    """
    
    metrics = await service.extract_financial_metrics_from_text(sample_text, use_ai=False)
    
    assert metrics["revenue"] == 836
    assert metrics["customers"] == 138
    assert metrics["cash"] == 250
    assert metrics["gross_margin"] == 75


@pytest.mark.asyncio
async def test_fallback_commentary():
    """Test fallback commentary when API unavailable."""
    service = GeminiAnalysisService()
    
    metrics = {
        "revenue": 836,
        "customers": 138,
        "cash": 250,
        "ebitda": 120,
        "gross_margin": 75,
        "operating_margin": 45,
    }
    
    commentary = service._generate_fallback_commentary(metrics, "TestCo")
    
    assert "TestCo" in commentary
    assert "836" in commentary or "836,000" in commentary


@pytest.mark.asyncio
async def test_text_chunking():
    """Test text chunking for large documents."""
    service = GeminiAnalysisService()
    
    long_text = "Sample text. " * 1000
    chunks = service._chunk_text(long_text, chunk_size=1000)
    
    assert len(chunks) > 1
    assert all(len(chunk) <= 1100 for chunk in chunks)  # Allow some overage


def test_multiplier_parsing():
    """Test unit multiplier parsing."""
    assert GeminiAnalysisService._get_multiplier("k") == 1e3
    assert GeminiAnalysisService._get_multiplier("m") == 1e6
    assert GeminiAnalysisService._get_multiplier("b") == 1e9
    assert GeminiAnalysisService._get_multiplier(None) == 1.0


@pytest.mark.asyncio
async def test_caching():
    """Test response caching."""
    service = GeminiAnalysisService(enable_cache=True)
    
    sample_text = "Revenue: €500K, Customers: 50"
    
    # First call
    result1 = await service.extract_financial_metrics_from_text(sample_text, use_ai=False)
    
    # Second call (should be cached)
    result2 = await service.extract_financial_metrics_from_text(sample_text, use_ai=False)
    
    assert result1 == result2