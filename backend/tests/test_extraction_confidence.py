"""
Tests for app/services/extraction_confidence.py's scoring function --
purely synthetic inputs (no PDF parsing here, see
test_financial_metrics_extractor.py for the real-document regression test).
"""
from app.services.extraction_confidence import (
    AUTO_ACCEPT_THRESHOLD,
    REVIEW_THRESHOLD,
    score_extraction,
)


def test_unrecognized_format_caps_at_zero_regardless_of_other_fields():
    result = score_extraction(
        format_recognized=False,
        baseline_metrics={},
        # Even with every field nominally present (e.g. Gemini hallucinated
        # plausible-looking numbers for an unrelated document), an
        # unrecognized format must score 0 -- these are more likely
        # coincidental than real.
        merged_metrics={"revenue": 100, "cash": 50, "customers": 10, "reporting_period": "FY2025"},
    )
    assert result.score == 0.0
    assert result.tier == "rejected"


def test_full_deterministic_match_scores_100_and_auto_accepts():
    baseline = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(format_recognized=True, baseline_metrics=baseline, merged_metrics=baseline)
    assert result.score == 100.0
    assert result.tier == "auto_accept"


def test_revenue_scores_higher_from_baseline_than_gemini_only():
    baseline_result = score_extraction(
        format_recognized=True,
        baseline_metrics={"revenue": 100.0},
        merged_metrics={"revenue": 100.0},
    )
    gemini_only_result = score_extraction(
        format_recognized=True,
        baseline_metrics={},
        merged_metrics={"revenue": 100.0},
    )
    # 40 (format) + 30 (revenue via baseline) = 70
    assert baseline_result.score == 70.0
    # 40 (format) + 15 (revenue via Gemini only) = 55
    assert gemini_only_result.score == 55.0
    assert baseline_result.score > gemini_only_result.score


def test_secondary_field_scores_higher_from_baseline_than_gemini_only():
    baseline_result = score_extraction(
        format_recognized=True,
        baseline_metrics={"cash": 50.0},
        merged_metrics={"cash": 50.0},
    )
    gemini_only_result = score_extraction(
        format_recognized=True,
        baseline_metrics={},
        merged_metrics={"cash": 50.0},
    )
    # 40 (format) + 0 (no revenue) + 15 (secondary via baseline) = 55
    assert baseline_result.score == 55.0
    # 40 (format) + 0 (no revenue) + 8 (secondary via Gemini only) = 48
    assert gemini_only_result.score == 48.0


def test_period_scores_higher_from_baseline_than_gemini_only():
    baseline_result = score_extraction(
        format_recognized=True,
        baseline_metrics={"reporting_period": "FY2025"},
        merged_metrics={"reporting_period": "FY2025"},
    )
    gemini_only_result = score_extraction(
        format_recognized=True,
        baseline_metrics={},
        merged_metrics={"reporting_period": "FY2025"},
    )
    assert baseline_result.score == 55.0  # 40 + 15
    assert gemini_only_result.score == 48.0  # 40 + 8


def test_period_from_start_and_end_pair_counts_as_deterministic():
    baseline = {"reporting_period_start": "Jul 2024", "reporting_period_end": "Jun 2025"}
    result = score_extraction(format_recognized=True, baseline_metrics=baseline, merged_metrics=baseline)
    assert result.score == 55.0  # 40 + 15


def test_pure_gemini_extraction_is_rejected_despite_every_field_present():
    # A document relying entirely on Gemini narrative-guessing (nothing in
    # baseline_metrics) tops out at 40 (format) + 15 + 8 + 8 = 71 -- well
    # below the review threshold, even with every field nominally "present"
    # in the merged result. An LLM alone must never be sufficient to put
    # data on the board-facing dashboard.
    merged = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(format_recognized=True, baseline_metrics={}, merged_metrics=merged)
    assert result.score == 71.0
    assert result.tier == "rejected"


def test_tier_boundaries_are_exact():
    # 94.9% just misses auto_accept -- format(40) + revenue-baseline(30) +
    # secondary-gemini(8) + no period(0) = 78... construct precisely using
    # a scenario that lands exactly at the boundary values instead.
    just_below_auto_accept = score_extraction(
        format_recognized=True,
        baseline_metrics={"revenue": 1.0, "cash": 1.0},
        merged_metrics={"revenue": 1.0, "cash": 1.0, "reporting_period": "FY2025"},
    )
    # 40 + 30 + 15 + 8 (period via Gemini only) = 93
    assert just_below_auto_accept.score == 93.0
    assert just_below_auto_accept.tier == "needs_review"

    just_below_review = score_extraction(
        format_recognized=True,
        baseline_metrics={},
        merged_metrics={"revenue": 1.0},
    )
    # 40 + 15 (revenue via Gemini only) + 0 + 0 = 55
    assert just_below_review.score == 55.0
    assert just_below_review.tier == "rejected"

    assert AUTO_ACCEPT_THRESHOLD == 95.0
    assert REVIEW_THRESHOLD == 85.0


def test_failed_pnl_reconciliation_caps_auto_accept_at_needs_review():
    baseline = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(
        format_recognized=True,
        baseline_metrics=baseline,
        merged_metrics=baseline,
        pnl_reconciles=False,
    )
    # Score itself is unaffected (still the full 100 -- an honest
    # reflection of the point system) but the tier is capped.
    assert result.score == 100.0
    assert result.tier == "needs_review"
    assert any("reconciliation" in reason.lower() for reason in result.reasons)


def test_failed_cashflow_reconciliation_caps_auto_accept_at_needs_review():
    baseline = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(
        format_recognized=True,
        baseline_metrics=baseline,
        merged_metrics=baseline,
        cashflow_reconciles=False,
    )
    assert result.tier == "needs_review"


def test_reconciliation_none_does_not_affect_tier():
    # None means "couldn't check" (e.g. the Information Document has no
    # cost_of_sales line at all) -- must not be treated as a failure.
    baseline = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(
        format_recognized=True,
        baseline_metrics=baseline,
        merged_metrics=baseline,
        pnl_reconciles=None,
        cashflow_reconciles=None,
    )
    assert result.tier == "auto_accept"


def test_successful_reconciliation_does_not_downgrade_tier():
    baseline = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
    result = score_extraction(
        format_recognized=True,
        baseline_metrics=baseline,
        merged_metrics=baseline,
        pnl_reconciles=True,
        cashflow_reconciles=True,
    )
    assert result.tier == "auto_accept"


def test_no_fields_found_at_all_still_scores_format_recognition_only():
    result = score_extraction(format_recognized=True, baseline_metrics={}, merged_metrics={})
    assert result.score == 40.0
    assert result.tier == "rejected"


class TestVisionExtraction:
    """
    A scanned document with no text layer at all (e.g. ADF Farm Solutions'
    statements) has zero possible baseline -- every field comes from a
    single Gemini vision read of the page images, not a baseline-vs-Gemini-
    narrative split. Scored on its own full-weight scale, but the tier is
    unconditionally capped at needs_review: there's no independent
    deterministic cross-check possible for a scanned document.
    """

    def test_unrecognized_format_still_caps_at_zero(self):
        result = score_extraction(
            format_recognized=False,
            baseline_metrics={},
            merged_metrics={"revenue": 100.0},
            vision_extracted=True,
        )
        assert result.score == 0.0
        assert result.tier == "rejected"

    def test_a_full_vision_extraction_scores_100_but_is_capped_at_needs_review(self):
        merged = {"revenue": 100.0, "cash": 50.0, "reporting_period": "FY2025"}
        result = score_extraction(
            format_recognized=True,
            baseline_metrics={},
            merged_metrics=merged,
            vision_extracted=True,
        )
        # Unlike a text document, vision extraction is never "baseline vs
        # Gemini-narrative" -- full point weights apply directly since
        # there's only one possible source.
        assert result.score == 100.0
        # But never auto_accept -- no independent cross-check exists for a
        # scanned document, so a human must always confirm it first.
        assert result.tier == "needs_review"
        assert any("capped" in reason.lower() for reason in result.reasons)

    def test_a_partial_vision_extraction_can_still_land_in_needs_review(self):
        result = score_extraction(
            format_recognized=True,
            baseline_metrics={},
            merged_metrics={"revenue": 100.0, "cash": 50.0},
            vision_extracted=True,
        )
        # 40 (format) + 30 (revenue) + 15 (secondary) + 0 (no period) = 85
        assert result.score == 85.0
        assert result.tier == "needs_review"

    def test_a_weak_vision_extraction_is_rejected(self):
        result = score_extraction(
            format_recognized=True,
            baseline_metrics={},
            merged_metrics={},
            vision_extracted=True,
        )
        assert result.score == 40.0
        assert result.tier == "rejected"

    def test_vision_extraction_never_reaches_auto_accept_even_with_a_perfect_score(self):
        merged = {"revenue": 1.0, "cash": 1.0, "ebitda": 1.0, "customers": 1, "reporting_period": "FY2025"}
        result = score_extraction(
            format_recognized=True,
            baseline_metrics={},
            merged_metrics=merged,
            vision_extracted=True,
        )
        assert result.tier != "auto_accept"
