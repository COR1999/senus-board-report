"""
Tests for GeminiAnalysisService's error-handling paths, particularly
distinguishing a transient rate-limit 429 from a permanent billing-
exhaustion 429 (found via direct testing against the real API -- see
frontend/docs/ai-usage/gemini-integration-fix.md).
"""
import time

import pytest

from app.services.gemini_service import GeminiAnalysisService


def _reset_class_state():
    """
    _ai_disabled_until, _call_timestamps, etc. are class attributes shared
    across every instance -- reset them before each test so one test's
    backoff doesn't leak into the next.
    """
    GeminiAnalysisService._ai_disabled_until = 0
    GeminiAnalysisService._call_timestamps.clear()
    GeminiAnalysisService._daily_call_count = 0
    GeminiAnalysisService._daily_window_started = 0.0
    GeminiAnalysisService._cache.clear()


@pytest.fixture(autouse=True)
def reset_state():
    _reset_class_state()
    yield
    _reset_class_state()


class _FakeModels:
    def __init__(self, error: Exception):
        self._error = error

    def generate_content(self, **kwargs):
        raise self._error


class _FakeClient:
    def __init__(self, error: Exception):
        self.models = _FakeModels(error)


def _service_with_client_raising(error: Exception) -> GeminiAnalysisService:
    svc = GeminiAnalysisService(api_key="fake-key-for-test")
    svc.client = _FakeClient(error)
    return svc


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModelsReturning:
    def __init__(self, text: str):
        self.calls = []
        self._text = text

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


def _service_with_client_returning(text: str) -> tuple[GeminiAnalysisService, _FakeModelsReturning]:
    svc = GeminiAnalysisService(api_key="fake-key-for-test")
    fake_models = _FakeModelsReturning(text)
    svc.client = type("FakeClient", (), {"models": fake_models})()
    return svc, fake_models


class TestBillingExhaustedBackoff:
    def test_billing_exhausted_error_backs_off_much_longer_than_rate_limit(self):
        error = Exception(
            "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
            "'Your prepayment credits are depleted. Please go to AI Studio...'}}"
        )
        svc = _service_with_client_raising(error)

        result = svc.generate_report("some prompt")

        assert result["model_version"] == "gemini-unavailable"
        assert not svc.is_available()
        # Backed off close to the full billing-exhausted duration (not the
        # short 60s rate-limit one) -- allow a little slack for test runtime.
        remaining = GeminiAnalysisService._ai_disabled_until - time.time()
        assert remaining > GeminiAnalysisService.RATE_LIMIT_BACKOFF_SECONDS

    def test_plain_rate_limit_429_uses_the_short_backoff(self):
        error = Exception("429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric.")
        svc = _service_with_client_raising(error)

        svc.generate_report("some prompt")

        remaining = GeminiAnalysisService._ai_disabled_until - time.time()
        assert 0 < remaining <= GeminiAnalysisService.RATE_LIMIT_BACKOFF_SECONDS

    def test_ordinary_quota_429_mentioning_billing_boilerplate_still_uses_short_backoff(self):
        # Regression test: a routine RESOURCE_EXHAUSTED daily-quota message
        # includes "please check your plan and billing details" as
        # standard Google API boilerplate -- a bare `"billing" in
        # error_str.lower()` check used to match this and misclassify it
        # as a billing-exhausted outage (24h backoff) instead of an
        # ordinary rate limit (60s backoff). This is the real message
        # captured from the live API for a free-tier daily cap hit.
        error = Exception(
            "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
            "'You exceeded your current quota, please check your plan and "
            "billing details. Quota exceeded for metric: "
            "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
            "limit: 20.', 'status': 'RESOURCE_EXHAUSTED'}}"
        )
        svc = _service_with_client_raising(error)

        svc.generate_report("some prompt")

        remaining = GeminiAnalysisService._ai_disabled_until - time.time()
        assert 0 < remaining <= GeminiAnalysisService.RATE_LIMIT_BACKOFF_SECONDS

    def test_non_429_error_does_not_trigger_any_backoff(self):
        error = Exception("500 Internal Server Error")
        svc = _service_with_client_raising(error)

        svc.generate_report("some prompt")

        assert GeminiAnalysisService._ai_disabled_until == 0
        assert svc.is_available()

    def test_returns_safe_fallback_shape_on_any_error(self):
        svc = _service_with_client_raising(Exception("boom"))
        result = svc.generate_report("some prompt")

        assert result["ai_commentary"] == "AI unavailable or failed (safe fallback)."
        # None, not a fabricated 0 -- this fallback fires exactly when the
        # deterministic baseline is incomplete (see report_service._generate,
        # which only calls Gemini at all when _baseline_is_complete is
        # False), so a `0` here would silently override a genuinely-missing
        # baseline field with a fake zero in the merge. Real bug found by
        # testing against the real Information Document filing (its
        # undisclosed EBITDA came back as 0 instead of null).
        assert result["financial_metrics"]["revenue"] is None
        assert result["financial_metrics"]["ebitda"] is None
        assert result["financial_metrics"]["customers"] is None


class TestGenerateReportFromImages:
    """
    generate_report_from_images is the backup path for a scanned document
    with no text layer at all (see report_service._generate) -- must go
    through the exact same rate-limit/backoff/cache machinery as the text
    path (_call_gemini, shared by both), not a separate, unguarded call.
    """

    def test_sends_the_prompt_and_every_image_as_multimodal_parts(self):
        svc, fake_models = _service_with_client_returning(
            '{"financial_metrics": {"revenue": {"value": 100}}}'
        )

        svc.generate_report_from_images([b"page-1-bytes", b"page-2-bytes"], "adf.pdf")

        assert len(fake_models.calls) == 1
        contents = fake_models.calls[0]["contents"]
        # First element is the text prompt, followed by one Part per image.
        assert isinstance(contents[0], str)
        assert len(contents) == 3

    def test_result_is_cached_by_image_bytes_and_context_together(self):
        svc, fake_models = _service_with_client_returning(
            '{"financial_metrics": {"revenue": {"value": 100}}}'
        )

        svc.generate_report_from_images([b"page-1-bytes"], "adf.pdf")
        svc.generate_report_from_images([b"page-1-bytes"], "adf.pdf")

        assert len(fake_models.calls) == 1

    def test_different_images_are_not_cache_collisions(self):
        svc, fake_models = _service_with_client_returning(
            '{"financial_metrics": {"revenue": {"value": 100}}}'
        )

        svc.generate_report_from_images([b"page-1-bytes"], "adf.pdf")
        svc.generate_report_from_images([b"a-completely-different-page"], "adf.pdf")

        assert len(fake_models.calls) == 2

    def test_billing_exhausted_error_disables_the_vision_path_too(self):
        # Same shared _call_gemini machinery as the text path -- a billing
        # error hit via generate_report_from_images must back off exactly
        # like one hit via generate_report (they share one circuit breaker,
        # not two independent ones that could each keep retrying).
        error = Exception(
            "429 RESOURCE_EXHAUSTED. Your prepayment credits are depleted. Please go to AI Studio..."
        )
        svc = _service_with_client_raising(error)

        result = svc.generate_report_from_images([b"page-1-bytes"], "adf.pdf")

        assert result["model_version"] == "gemini-unavailable"
        assert not svc.is_available()

    def test_returns_empty_response_when_gemini_is_already_disabled(self):
        svc, fake_models = _service_with_client_returning("{}")
        GeminiAnalysisService._ai_disabled_until = time.time() + 1000

        result = svc.generate_report_from_images([b"page-1-bytes"], "adf.pdf")

        assert result["model_version"] == "gemini-unavailable"
        assert fake_models.calls == []
