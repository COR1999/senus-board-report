from __future__ import annotations

import logging
import os
import time
import json
import hashlib
import re
from typing import Optional, Dict, Any

from cachetools import TTLCache
from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


class GeminiAnalysisService:
    """
    CLEAN AI SERVICE ONLY:
    - Gemini API calls
    - caching
    - quota handling
    - safe JSON parsing
    """

    _cache = TTLCache(maxsize=1000, ttl=86400)
    _ai_disabled_until: float = 0

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client: Any | None = None

        if not self.api_key:
            logger.warning("GEMINI_API_KEY missing")
            return

        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Gemini client initialized")
        except Exception as e:
            logger.warning(f"Gemini init failed: {e}")
            self.client = None

    # =========================================================
    # STATUS
    # =========================================================
    def is_available(self) -> bool:
        return (
            self.client is not None
            and time.time() >= self._ai_disabled_until
        )

    def _disable_ai_temporarily(self, seconds: int = 60):
        self._ai_disabled_until = time.time() + seconds
        logger.warning(f"Gemini disabled for {seconds}s (quota)")

    # =========================================================
    # CACHE
    # =========================================================
    def _cache_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        return self._cache.get(key)

    def _set_cache(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = value

    # =========================================================
    # PUBLIC ENTRY POINT
    # =========================================================
    def generate_report(self, prompt: str) -> Dict[str, Any]:

        # AI unavailable -> safe fallback (EMPTY STRUCTURE, NOT regex here)
        if not self.is_available():
            return self._empty_response()
        if self.client is None:
            return self._empty_response()

        client: genai.Client = self.client

        cache_key = self._cache_key(prompt)
        cached = self._get_cache(cache_key)
        if isinstance(cached, dict):
            return cached

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1200,
                ),
            )

            result = self._parse(response.text or "")

            self._set_cache(cache_key, result)
            return result

        except Exception as e:
            logger.warning(f"Gemini error: {e}")

            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                self._disable_ai_temporarily(60)

            return self._empty_response()

    # =========================================================
    # PARSING
    # =========================================================
    def _parse(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if not match:
            return self._empty_response()

        try:
            data = json.loads(match.group())
            return data if isinstance(data, dict) else self._empty_response()
        except json.JSONDecodeError:
            return self._empty_response()

    # =========================================================
    # FALLBACK (SAFE EMPTY STRUCTURE ONLY)
    # =========================================================
    def _empty_response(self) -> Dict[str, Any]:
        return {
            "company_name": None,
            "reporting_period": None,
            "financial_metrics": {
                "revenue": 0,
                "cash": 0,
                "ebitda": 0,
                "customers": 0,
                "gross_margin": 0,
                "operating_margin": 0,
            },
            "key_findings": [],
            "ai_commentary": "AI unavailable or failed (safe fallback).",
            "model_version": "gemini-unavailable",
        }