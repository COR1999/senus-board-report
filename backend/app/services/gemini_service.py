"""
Google Gemini AI Service for Financial Metrics Extraction and Report Generation.
Handles API communication, caching, rate limiting, and error recovery.
"""

import logging
import json
import re
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib
import os

import google.genai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from cachetools import TTLCache

logger = logging.getLogger(__name__)


class GeminiModel(str, Enum):
    """Available Gemini models."""
    FLASH = "gemini-1.5-flash"
    PRO = "gemini-1.5-pro"


class MetricType(str, Enum):
    """Financial metric types for extraction."""
    REVENUE = "revenue"
    CUSTOMERS = "customers"
    CASH = "cash"
    EBITDA = "ebitda"
    GROSS_MARGIN = "gross_margin"
    OPERATING_MARGIN = "operating_margin"


class GeminiAnalysisService:
    """
    Service for Gemini-based financial analysis.
    
    Responsibilities:
    - Extract financial metrics from PDF text
    - Generate AI commentary and summaries
    - Handle API errors with exponential backoff
    - Cache results to minimize API calls
    """

    # Cache config: 1000 entries, 24-hour TTL
    _cache = TTLCache(maxsize=1000, ttl=86400)
    
    # Gemini API limits
    MAX_TOKENS_PER_REQUEST = 100000
    CHUNK_SIZE = 30000  # Characters per chunk
    REQUEST_TIMEOUT = 60  # seconds

    def __init__(self, api_key: Optional[str] = None, enable_cache: bool = True):
        """
        Initialize Gemini service with new google.genai API.
        
        Args:
            api_key: Google Gemini API key (uses env var if not provided)
            enable_cache: Enable result caching
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.enable_cache = enable_cache
        self._initialized = False
        self.client = None
        
        try:
            if self.api_key:
                # Initialize new google.genai Client
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized successfully")
                self._initialized = True
            else:
                logger.warning("GEMINI_API_KEY not found in environment variables")
                self._initialized = False
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini client: {e}")
            self._initialized = False

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        return self._initialized and self.client is not None

    def _get_cache_key(self, method: str, content: str) -> str:
        """Generate cache key from method and content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{method}:{content_hash}"

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        if not self.enable_cache:
            return None
        return self._cache.get(key)

    def _set_cache(self, key: str, value: Any) -> None:
        """Store value in cache."""
        if self.enable_cache:
            self._cache[key] = value

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def _call_gemini_api(
        self,
        prompt: str,
        model: GeminiModel = GeminiModel.FLASH,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Call Gemini API with retry logic using new google.genai package.
        
        Args:
            prompt: The prompt to send to Gemini
            model: Model to use
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If API call fails after retries
        """
        if not self.is_available():
            raise RuntimeError("Gemini API not available")

        try:
            logger.debug(f"Calling Gemini API with model {model.value}")

            # Use asyncio.to_thread to run sync API call in thread pool
            response = await asyncio.to_thread(
                self._call_gemini_sync,
                model,
                prompt,
                temperature,
                max_tokens,
            )

            if not response:
                logger.warning("Empty response from Gemini API")
                return ""

            logger.debug(f"Gemini API response length: {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"Error occurred while calling Gemini API: {e}")
            raise

    def _call_gemini_sync(
        self,
        model: GeminiModel,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Synchronous wrapper for Gemini API call.
        Used with asyncio.to_thread to avoid blocking.
        """
        if self.client is None:
            raise RuntimeError("Gemini client is not initialized")

        response = self.client.models.generate_content(
            model=model.value,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        
        # Extract text from response, handle possible None values
        if hasattr(response, 'text'):
            text = getattr(response, 'text')
            if text is not None:
                return text
        if hasattr(response, 'content'):
            content = getattr(response, 'content')
            if content is not None:
                return content
        # Fallback to string representation
        return str(response)

    def _chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
        """
        Split large text into chunks for processing.
        
        Args:
            text: Text to chunk
            chunk_size: Character size per chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start, end)
                if last_period > start:
                    end = last_period + 1
            
            chunks.append(text[start:end].strip())
            start = end
        
        return [c for c in chunks if c]  # Filter empty chunks

    def _parse_financial_metrics(
        self,
        extracted_text: str,
    ) -> Dict[str, Optional[float]]:
        """
        Extract financial metrics from text using regex and pattern matching.
        
        This is the fallback when Gemini API is unavailable or as first pass.
        
        Args:
            extracted_text: Extracted PDF text
            
        Returns:
            Dictionary with metric values
        """
        metrics: Dict[str, Optional[float]] = {
            "revenue": None,
            "customers": None,
            "cash": None,
            "ebitda": None,
            "gross_margin": None,
            "operating_margin": None,
        }

        if not extracted_text:
            return metrics

        text = extracted_text.lower()

        # Revenue patterns (€, $, million, thousand)
        revenue_patterns = [
            r"revenue[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
            r"annual\s+revenue[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
            r"total\s+revenue[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                multiplier = self._get_multiplier(match.group(2))
                metrics["revenue"] = value * multiplier
                break

        # Customers/Users patterns
        customer_patterns = [
            r"(?:customers?|users?)[:\s]+(\d+(?:\,\d{3})*)",
            r"(\d+(?:\,\d{3})*)\s+(?:customers?|users?)",
        ]
        
        for pattern in customer_patterns:
            match = re.search(pattern, text)
            if match:
                metrics["customers"] = float(match.group(1).replace(",", ""))
                break

        # Cash patterns
        cash_patterns = [
            r"cash[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
            r"(?:total\s+)?cash[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
        ]
        
        for pattern in cash_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                multiplier = self._get_multiplier(match.group(2))
                metrics["cash"] = value * multiplier
                break

        # EBITDA patterns
        ebitda_patterns = [
            r"ebitda[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
            r"(?:adjusted\s+)?ebitda[:\s]+€?\$?(\d+\.?\d*)\s*(m|k|b)?(?:illion)?",
        ]
        
        for pattern in ebitda_patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                multiplier = self._get_multiplier(match.group(2))
                metrics["ebitda"] = value * multiplier
                break

        # Margin patterns (percentage)
        margin_patterns = [
            (r"gross\s+margin[:\s]+(\d+\.?\d*)%?", "gross_margin"),
            (r"operating\s+margin[:\s]+(\d+\.?\d*)%?", "operating_margin"),
        ]
        
        for pattern, metric_name in margin_patterns:
            match = re.search(pattern, text)
            if match:
                metrics[metric_name] = float(match.group(1))

        logger.info(f"Extracted metrics via regex: {metrics}")
        return metrics

    @staticmethod
    def _get_multiplier(unit: Optional[str]) -> float:
        """Get numeric multiplier for unit (k, m, b)."""
        if not unit:
            return 1.0
        unit = unit.lower()
        multipliers = {"k": 1e3, "m": 1e6, "b": 1e9}
        return multipliers.get(unit, 1.0)

    async def extract_financial_metrics_from_text(
        self,
        extracted_text: str,
        use_ai: bool = True,
    ) -> Dict[str, Optional[float]]:
        """
        Extract financial metrics from PDF text.
        
        Uses two-step approach:
        1. Regex-based extraction (fast, reliable)
        2. AI-based extraction (more accurate for complex formats)
        
        Args:
            extracted_text: Extracted PDF text
            use_ai: Whether to use Gemini for extraction
            
        Returns:
            Dictionary with extracted metrics
        """
        if not extracted_text:
            logger.warning("No text provided for metric extraction")
            return {
                "revenue": None,
                "customers": None,
                "cash": None,
                "ebitda": None,
                "gross_margin": None,
                "operating_margin": None,
            }

        # Check cache first
        cache_key = self._get_cache_key("extract_metrics", extracted_text)
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info("Returning cached metrics")
            return cached

        # Step 1: Try regex extraction first (fast)
        metrics = self._parse_financial_metrics(extracted_text)
        
        # Step 2: Use AI to fill in missing metrics or validate
        if use_ai and self.is_available():
            try:
                ai_metrics = await self._extract_metrics_with_ai(extracted_text)
                # Merge, preferring AI results for empty fields
                for key in metrics:
                    if metrics[key] is None and ai_metrics.get(key) is not None:
                        metrics[key] = ai_metrics[key]
            except Exception as e:
                logger.warning(f"AI extraction failed, using regex results: {e}")

        self._set_cache(cache_key, metrics)
        return metrics

    async def _extract_metrics_with_ai(
        self,
        extracted_text: str,
    ) -> Dict[str, Optional[float]]:
        """
        Use Gemini to extract financial metrics.
        
        Args:
            extracted_text: Extracted PDF text
            
        Returns:
            Dictionary with extracted metrics
        """
        # Chunk text if too long
        chunks = self._chunk_text(extracted_text)
        full_text = " ".join(chunks[:3])  # Use first 3 chunks

        prompt = f"""Analyze the following financial document text and extract key financial metrics.
Return ONLY a JSON object with these fields (use null for missing values):
{{
    "revenue": <number in thousands>,
    "customers": <number>,
    "cash": <number in thousands>,
    "ebitda": <number in thousands>,
    "gross_margin": <percentage number 0-100>,
    "operating_margin": <percentage number 0-100>
}}

Document text:
{full_text[:4000]}"""

        try:
            response = await self._call_gemini_api(
                prompt=prompt,
                model=GeminiModel.FLASH,
                temperature=0.1,  # Low temperature for structured output
                max_tokens=500,
            )

            # Parse JSON response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    logger.info(f"AI extracted metrics: {parsed}")
                    return parsed
                except json.JSONDecodeError:
                    logger.warning("Failed to parse AI response as JSON")

        except Exception as e:
            logger.warning(f"AI metric extraction failed: {e}")

        return {
            "revenue": None,
            "customers": None,
            "cash": None,
            "ebitda": None,
            "gross_margin": None,
            "operating_margin": None,
        }

    async def generate_ai_commentary(
        self,
        extracted_text: str,
        metrics: Dict[str, Optional[float]],
        company_name: Optional[str] = None,
    ) -> str:
        """
        Generate executive summary and insights using Gemini.
        
        Args:
            extracted_text: Extracted PDF text
            metrics: Extracted financial metrics
            company_name: Company name for context
            
        Returns:
            AI-generated commentary
        """
        if not extracted_text:
            return "No text available for analysis."

        # Check cache
        cache_key = self._get_cache_key("commentary", extracted_text)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        if not self.is_available():
            logger.warning("Gemini API not available, returning fallback commentary")
            return self._generate_fallback_commentary(metrics, company_name)

        try:
            # Prepare summary of metrics for context
            metrics_summary = self._format_metrics_for_prompt(metrics)
            
            # Chunk text
            chunks = self._chunk_text(extracted_text)
            summary_text = " ".join(chunks[:2])  # Use first 2 chunks

            prompt = f"""As a financial analyst, review this company document and provide a concise executive summary.

Company: {company_name or 'Unknown'}

Key Metrics:
{metrics_summary}

Document excerpt:
{summary_text[:3000]}

Provide a 3-4 paragraph executive summary highlighting:
1. Business overview and key strengths
2. Financial performance and trends
3. Notable metrics and insights
4. Key risks or considerations

Be professional, concise, and data-driven."""

            commentary = await self._call_gemini_api(
                prompt=prompt,
                model=GeminiModel.FLASH,
                temperature=0.7,
                max_tokens=1500,
            )

            self._set_cache(cache_key, commentary)
            return commentary

        except Exception as e:
            logger.error(f"Failed to generate AI commentary: {e}")
            return self._generate_fallback_commentary(metrics, company_name)

    async def generate_report_summary(
        self,
        extracted_text: str,
        metrics: Dict[str, Optional[float]],
    ) -> List[str]:
        """
        Generate bullet-point summary of key findings.
        
        Args:
            extracted_text: Extracted PDF text
            metrics: Extracted financial metrics
            
        Returns:
            List of bullet-point summaries
        """
        cache_key = self._get_cache_key("summary", extracted_text)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        if not self.is_available():
            return self._generate_fallback_summary(metrics)

        try:
            chunks = self._chunk_text(extracted_text)
            summary_text = " ".join(chunks[:2])

            metrics_summary = self._format_metrics_for_prompt(metrics)

            prompt = f"""Analyze this document and create 5-7 key findings as bullet points.

Key Metrics:
{metrics_summary}

Document:
{summary_text[:3000]}

Return ONLY a JSON array of strings with key findings. Example format:
["Finding 1: details", "Finding 2: details", ...]

Each bullet should be one clear statement about business, financials, or operations."""

            response = await self._call_gemini_api(
                prompt=prompt,
                model=GeminiModel.FLASH,
                temperature=0.5,
                max_tokens=800,
            )

            # Parse JSON array
            json_match = re.search(r"$$.*$$", response, re.DOTALL)
            if json_match:
                try:
                    bullets = json.loads(json_match.group())
                    if isinstance(bullets, list):
                        self._set_cache(cache_key, bullets)
                        return bullets
                except json.JSONDecodeError:
                    logger.warning("Failed to parse summary as JSON")

            return self._generate_fallback_summary(metrics)

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return self._generate_fallback_summary(metrics)

    @staticmethod
    def _format_metrics_for_prompt(metrics: Dict[str, Optional[float]]) -> str:
        """Format metrics dictionary for prompt context."""
        formatted = []
        for key, value in metrics.items():
            if value is not None:
                unit = "%" if "margin" in key else "K€" if key in ["revenue", "cash", "ebitda"] else ""
                formatted.append(f"- {key.replace('_', ' ').title()}: {value:,.2f}{unit}")
        
        return "\n".join(formatted) if formatted else "No metrics available"

    def _generate_fallback_commentary(
        self,
        metrics: Dict[str, Optional[float]],
        company_name: Optional[str] = None,
    ) -> str:
        """Generate fallback commentary when API unavailable."""
        company = company_name or "the company"
        
        commentary = f"**Financial Overview**\n\n"
        commentary += f"{company} has submitted financial documentation for analysis. "
        
        if metrics.get("revenue"):
            commentary += f"Annual revenue stands at €{metrics['revenue']:,.0f}K. "
        
        if metrics.get("customers"):
            commentary += f"The company serves {metrics['customers']:,.0f} customers. "
        
        if metrics.get("ebitda"):
            commentary += f"EBITDA is reported at €{metrics['ebitda']:,.0f}K. "
        
        commentary += "\n\nDetailed analysis with AI commentary will be available when the Gemini API is operational."
        
        return commentary

    @staticmethod
    def _generate_fallback_summary(metrics: Dict[str, Optional[float]]) -> List[str]:
        """Generate fallback bullet points when API unavailable."""
        bullets = ["Document processed successfully"]
        
        if metrics.get("revenue"):
            bullets.append(f"Annual revenue: €{metrics['revenue']:,.0f}K")
        
        if metrics.get("customers"):
            bullets.append(f"Customer base: {metrics['customers']:,.0f}")
        
        if metrics.get("cash"):
            bullets.append(f"Available cash: €{metrics['cash']:,.0f}K")
        
        if metrics.get("ebitda"):
            bullets.append(f"EBITDA: €{metrics['ebitda']:,.0f}K")
        
        if metrics.get("gross_margin"):
            bullets.append(f"Gross margin: {metrics['gross_margin']:.1f}%")
        
        if metrics.get("operating_margin"):
            bullets.append(f"Operating margin: {metrics['operating_margin']:.1f}%")
        
        return bullets