from __future__ import annotations

import logging
import os
import time
import json
import hashlib
import re
from collections import deque
from typing import List, Optional, Dict, Any

from cachetools import TTLCache
from google import genai
from google.genai import types

# Matches _build_prompt's JSON contract in report_service.py exactly, so
# both the text and vision extraction paths feed _generate() the same
# shape -- scanning across every provided page image (a scanned document
# has no text layer to isolate a statement section from first, so the
# model has to locate the relevant table itself) rather than assuming
# page 1 has what's needed.
_VISION_EXTRACTION_PROMPT = """
You are a senior financial analyst reviewing scanned pages of a company's
financial statements (page images, in order).

Find the profit and loss / income statement, balance sheet, and cash flow
statement wherever they appear across these pages, and extract the
figures. If a figure is genuinely not disclosed anywhere in these pages,
leave it null -- never guess or estimate a value.

Return JSON ONLY, in exactly this shape:

{
  "company_name": "...",
  "reporting_period": "...",
  "financial_metrics": {
    "revenue": {"value": 0},
    "customers": {"value": 0},
    "cash": {"value": 0},
    "ebitda": {"value": 0},
    "gross_margin": {"value": 0},
    "operating_margin": {"value": 0}
  },
  "key_findings": [],
  "ai_commentary": ""
}
""".strip()


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

    # A 429 can mean two very different things: a transient per-minute/per-day
    # rate limit (will clear on its own -- short backoff is right), or the
    # Google AI Studio project's prepayment credits being depleted (a billing
    # problem that requires manual action and will NOT clear on its own --
    # retrying every 60s just wastes calls hitting the same exhausted quota
    # until someone tops up billing). Distinguished by message content since
    # the SDK doesn't expose a distinct error type for this.
    RATE_LIMIT_BACKOFF_SECONDS = 60
    BILLING_EXHAUSTED_BACKOFF_SECONDS = 24 * 60 * 60

    # Proactive rate limiting -- these back off BEFORE a 429 happens,
    # rather than only reacting after Gemini has already rejected a call.
    # Defaults are conservative guesses for a free-tier-ish quota; tune
    # via env vars to match your actual plan.
    MAX_CALLS_PER_MINUTE = int(os.getenv("GEMINI_MAX_CALLS_PER_MINUTE", "10"))
    MAX_CALLS_PER_DAY = int(os.getenv("GEMINI_MAX_CALLS_PER_DAY", "1000"))

    # Not hardcoded -- a pinned model version can lose free-tier quota
    # eligibility on Google's side with no code change on ours. Overriding
    # via env var means swapping models doesn't need a redeploy.
    MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    _call_timestamps: "deque[float]" = deque()
    _daily_call_count: int = 0
    _daily_window_started: float = 0.0

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
        GeminiAnalysisService._ai_disabled_until = time.time() + seconds
        logger.warning(f"Gemini disabled for {seconds}s (quota)")

    # =========================================================
    # PROACTIVE RATE LIMITING (per-minute + per-day)
    # =========================================================
    def _within_rate_limit(self) -> bool:
        now = time.time()

        if now - self._daily_window_started > 86400:
            GeminiAnalysisService._daily_window_started = now
            GeminiAnalysisService._daily_call_count = 0

        if self._daily_call_count >= self.MAX_CALLS_PER_DAY:
            logger.warning(
                f"Gemini daily call cap reached ({self.MAX_CALLS_PER_DAY}); "
                "falling back without calling the API"
            )
            return False

        while self._call_timestamps and now - self._call_timestamps[0] > 60:
            self._call_timestamps.popleft()

        if len(self._call_timestamps) >= self.MAX_CALLS_PER_MINUTE:
            logger.warning(
                f"Gemini per-minute call cap reached ({self.MAX_CALLS_PER_MINUTE}); "
                "falling back without calling the API"
            )
            return False

        return True

    def _record_call(self) -> None:
        now = time.time()
        GeminiAnalysisService._call_timestamps.append(now)
        GeminiAnalysisService._daily_call_count += 1

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
    # PUBLIC ENTRY POINTS
    # =========================================================
    def generate_report(self, prompt: str) -> Dict[str, Any]:
        return self._call_gemini(self._cache_key(prompt), prompt)

    def generate_report_from_images(self, images: List[bytes], context: str) -> Dict[str, Any]:
        """
        Same contract as generate_report, but for a scanned document with no
        text layer at all (see PDFExtractionService.render_page_images) --
        sends every page image in a single request rather than one call per
        page, so a many-page document still costs exactly one call. Only
        ever invoked from report_service.py when the deterministic
        extractor found literally nothing to parse (no text layer at all),
        never for a document a text-based extraction could already handle
        -- Gemini vision is a backup for when the other systems can't run
        at all, not a first resort.

        `context` (the filename) is folded into the cache key alongside the
        image bytes themselves, so re-processing the exact same scanned PDF
        (e.g. a regenerate) reuses the cached result instead of spending a
        second call.
        """
        digest = hashlib.sha256(context.encode())
        for image in images:
            digest.update(image)
        cache_key = digest.hexdigest()

        contents = [_VISION_EXTRACTION_PROMPT] + [
            types.Part.from_bytes(data=image, mime_type="image/jpeg") for image in images
        ]
        return self._call_gemini(cache_key, contents)

    # =========================================================
    # SHARED CALL PATH (used by both entry points above)
    # =========================================================
    def _call_gemini(self, cache_key: str, contents: Any) -> Dict[str, Any]:
        # AI unavailable -> safe fallback (EMPTY STRUCTURE, NOT regex here)
        if not self.is_available():
            return self._empty_response()
        if self.client is None:
            return self._empty_response()

        client: genai.Client = self.client

        cached = self._get_cache(cache_key)
        if isinstance(cached, dict):
            return cached

        # Proactive guard: stay under the quota ourselves instead of
        # waiting to get rejected with a 429.
        if not self._within_rate_limit():
            return self._empty_response()

        try:
            self._record_call()
            response = client.models.generate_content(
                model=self.MODEL,
                contents=contents,
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

            error_str = str(e)
            if "prepayment credits are depleted" in error_str or "billing" in error_str.lower():
                logger.error(
                    "Gemini API prepayment credits are depleted -- this needs manual "
                    "billing action at https://ai.studio/projects, not a transient rate "
                    f"limit. Backing off {self.BILLING_EXHAUSTED_BACKOFF_SECONDS}s "
                    "instead of the usual 60s so we don't keep re-hitting a quota that "
                    "won't recover on its own."
                )
                self._disable_ai_temporarily(self.BILLING_EXHAUSTED_BACKOFF_SECONDS)
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                self._disable_ai_temporarily(self.RATE_LIMIT_BACKOFF_SECONDS)

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
        # `None` for every field, not `0` -- a real bug found by testing:
        # this fallback fires whenever Gemini is unavailable/rate-limited/
        # fails, which is exactly when the deterministic baseline is
        # *incomplete* (report_service._generate only calls Gemini at all
        # when `_baseline_is_complete` is False). The old `0` defaults here
        # silently overrode a genuinely-missing baseline field (e.g. the
        # Information Document's undisclosed EBITDA) with a fabricated
        # zero in the merge, reproducing the exact "missing data becomes a
        # fake 0" bug already fixed once in report_service.py's
        # `_normalize_metric` -- this fallback just does it from a
        # different code path. `None` here lets baseline's real "not
        # disclosed" verdict stand instead of being silently overwritten.
        return {
            "company_name": None,
            "reporting_period": None,
            "financial_metrics": {
                "revenue": None,
                "cash": None,
                "ebitda": None,
                "customers": None,
                "gross_margin": None,
                "operating_margin": None,
            },
            "key_findings": [],
            "ai_commentary": "AI unavailable or failed (safe fallback).",
            "model_version": "gemini-unavailable",
        }