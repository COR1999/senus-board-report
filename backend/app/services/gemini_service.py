"""
Google Gemini AI Service – Clean & Modern Version with Quota Handling
"""

import logging
import re
import hashlib
import time
from typing import Optional, Dict, Any
from enum import Enum
import os

from cachetools import TTLCache
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiModel(str, Enum):
    FLASH = "gemini-2.0-flash"
    PRO = "gemini-1.5-pro"


class GeminiAnalysisService:
    _cache = TTLCache(maxsize=1000, ttl=86400)
    _ai_disabled_until: float = 0          # Class-level quota cooldown

    def __init__(self, api_key: Optional[str] = None, enable_cache: bool = True):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.enable_cache = enable_cache
        self.client = None
        self._initialized = False

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._initialized = True
                logger.info("✅ Gemini client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found in environment")

    def is_available(self) -> bool:
        """Returns True only if client exists and quota is not temporarily disabled."""
        if not self._initialized or self.client is None:
            return False
        if time.time() < self._ai_disabled_until:
            return False
        return True

    def _disable_ai_temporarily(self, seconds: int = 60):
        """Temporarily disable AI calls (used when quota is exceeded)."""
        self._ai_disabled_until = time.time() + seconds
        logger.warning(f"Gemini AI temporarily disabled for {seconds} seconds due to quota.")

    def _get_cache_key(self, method: str, content: str) -> str:
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{method}:{content_hash}"

    def _get_from_cache(self, key: str) -> Optional[Any]:
        return self._cache.get(key) if self.enable_cache else None

    def _set_cache(self, key: str, value: Any) -> None:
        if self.enable_cache:
            self._cache[key] = value

    async def extract_financial_metrics_from_text(
        self,
        extracted_text: str,
        use_ai: bool = True,
    ) -> Dict[str, Optional[float]]:
        """Main entry point for metric extraction."""
        if not extracted_text:
            return self._empty_metrics()

        cache_key = self._get_cache_key("metrics", extracted_text)
        if cached := self._get_from_cache(cache_key):
            return cached

        metrics = self._parse_financial_metrics(extracted_text)

        if use_ai and self.is_available():
            try:
                ai_metrics = await self._extract_with_ai(extracted_text)
                for key in metrics:
                    if metrics[key] is None and ai_metrics.get(key):
                        metrics[key] = ai_metrics[key]
            except Exception as e:
                logger.warning(f"AI extraction failed: {e}")

        self._set_cache(cache_key, metrics)
        return metrics

    def _empty_metrics(self) -> Dict[str, Optional[float]]:
        return {
            "revenue": None,
            "customers": None,
            "cash": None,
            "ebitda": None,
            "gross_margin": None,
            "operating_margin": None,
        }

    def _parse_financial_metrics(self, text: str) -> Dict[str, Optional[float]]:
        """Regex-based extraction"""
        metrics = self._empty_metrics()
        text = text.lower()

        # Revenue
        for pattern in [
            r"revenue[:\s]+[€$]?(\d+\.?\d*)\s*(m|k|b)?",
            r"annual revenue[:\s]+[€$]?(\d+\.?\d*)\s*(m|k|b)?",
        ]:
            if match := re.search(pattern, text):
                val = float(match.group(1))
                mul = {"k": 1000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2), 1)
                metrics["revenue"] = val * mul
                break

        # Customers
        if match := re.search(r"(?:customers?|users?)[:\s]+(\d+(?:,\d{3})*)", text):
            metrics["customers"] = float(match.group(1).replace(",", ""))

        # Cash
        if match := re.search(r"cash[:\s]+[€$]?(\d+\.?\d*)\s*(m|k|b)?", text):
            val = float(match.group(1))
            mul = {"k": 1000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2), 1)
            metrics["cash"] = val * mul

        # EBITDA
        if match := re.search(r"ebitda[:\s]+[€$]?(\d+\.?\d*)\s*(m|k|b)?", text):
            val = float(match.group(1))
            mul = {"k": 1000, "m": 1_000_000, "b": 1_000_000_000}.get(match.group(2), 1)
            metrics["ebitda"] = val * mul

        # Margins
        if match := re.search(r"gross\s+margin[:\s]+(\d+\.?\d*)%?", text):
            metrics["gross_margin"] = float(match.group(1))
        if match := re.search(r"operating\s+margin[:\s]+(\d+\.?\d*)%?", text):
            metrics["operating_margin"] = float(match.group(1))

        logger.info(f"Regex extracted: {metrics}")
        return metrics

    async def _extract_with_ai(self, text: str) -> Dict[str, Optional[float]]:
        """AI-based extraction using Gemini"""
        if not self.client:
            return self._empty_metrics()

        prompt = f"""Extract the following financial metrics from the text below.
Return ONLY valid JSON with these exact keys (use null if missing):

{{
  "revenue": number or null,
  "customers": number or null,
  "cash": number or null,
  "ebitda": number or null,
  "gross_margin": number or null,
  "operating_margin": number or null
}}

Text:
{text[:6000]}"""

        try:
            response = self.client.models.generate_content(
                model=GeminiModel.FLASH.value,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=800,
                ),
            )

            json_text = re.search(r"\{.*\}", response.text or "", re.DOTALL)
            if json_text:
                import json
                return json.loads(json_text.group())

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                self._disable_ai_temporarily(60)   # Disable AI for 60 seconds
            logger.warning(f"Gemini AI call failed: {e}")

        return self._empty_metrics()