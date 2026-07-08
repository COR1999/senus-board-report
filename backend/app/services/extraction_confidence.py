"""
Extraction confidence scoring.

Why this exists
----------------
A real production incident: importing a non-financial document (an AGM
notice) through the investor-relations sync feature produced a
`FinancialMetrics` row with every baseline figure defaulted to a fabricated
`0` (a separate bug, since fixed), and that row -- being the most recently
extracted -- silently became "the" dashboard data, blanking out the real
half-year filing. This module is the general-purpose fix: every PDF this
project processes, regardless of how it entered the system (manual upload,
investor-relations import, or a report regeneration), is scored here before
its extracted data is trusted.

There is no ML/statistical model backing this score -- none exists anywhere
in this pipeline, and inventing a fake continuous probability would itself
be a fabrication, the exact thing this project avoids everywhere else. This
is instead a transparent, fully-tested point system built directly from how
`FinancialMetricsExtractor` actually works: a value it found via a
structured table match is objectively more trustworthy than one Gemini
inferred from narrative text (see `_generate` in report_service.py, which
computes both `baseline_metrics` and the Gemini-merged result separately),
and a document that doesn't match any known financial-statement format at
all is scored zero outright, regardless of any narrative-regex "hits"
elsewhere in its text -- those are more likely to be coincidental than real.

Tiering matches standard IDP (Intelligent Document Processing) practice:
    >= 95%  auto_accept   -- reaches the executive dashboard immediately
    85-94%  needs_review  -- persisted, visible on the Documents/Reports
                             tables, but never selected as "latest" for the
                             dashboard's headline KPIs until it clears 95%
    < 85%   rejected       -- nothing is persisted at all
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

Tier = Literal["auto_accept", "needs_review", "rejected"]

AUTO_ACCEPT_THRESHOLD = 95.0
REVIEW_THRESHOLD = 85.0

# The three fields checked as a single "did we find at least one secondary
# figure" signal, alongside revenue (scored separately, as the anchor
# figure every ratio/margin derives from).
_SECONDARY_FIELDS = ("cash", "ebitda", "customers")


@dataclass(frozen=True)
class ExtractionConfidence:
    score: float  # 0-100, the raw point total (see module docstring)
    tier: Tier
    reasons: List[str]  # human-readable, shown in the 422 detail / review tag


class LowConfidenceExtractionError(Exception):
    """
    Raised by `ReportService._generate` when a document's extraction scores
    below `REVIEW_THRESHOLD` -- callers (the upload/import route, and the
    report-regenerate route) each decide their own consequence: a brand-new
    document is never persisted at all; a regenerate attempt leaves the
    document's existing (better) data untouched.
    """

    def __init__(self, confidence: ExtractionConfidence):
        self.confidence = confidence
        super().__init__(
            f"Extraction scored {confidence.score:.0f}% confidence "
            f"(below the {REVIEW_THRESHOLD:.0f}% threshold): {'; '.join(confidence.reasons)}"
        )


def _tier_for(score: float) -> Tier:
    if score >= AUTO_ACCEPT_THRESHOLD:
        return "auto_accept"
    if score >= REVIEW_THRESHOLD:
        return "needs_review"
    return "rejected"


def score_extraction(
    *,
    format_recognized: bool,
    baseline_metrics: Dict[str, Any],
    merged_metrics: Dict[str, Any],
    pnl_reconciles: Optional[bool] = None,
    cashflow_reconciles: Optional[bool] = None,
) -> ExtractionConfidence:
    """
    Scores one document's extraction result. `baseline_metrics` is the
    deterministic extractor's own output (`FinancialMetricsExtractor.
    extract()`); `merged_metrics` is the post-Gemini-merge result actually
    being saved (baseline always wins the merge, so a field present in
    `merged_metrics` but absent from `baseline_metrics` came from Gemini
    alone). `pnl_reconciles`/`cashflow_reconciles` come from
    `FinancialMetricsExtractor.check_reconciliation()` -- `None` when the
    document doesn't disclose enough to check (not a failure), `False`
    only on a genuine, confirmed arithmetic mismatch.
    """
    if not format_recognized:
        return ExtractionConfidence(
            score=0.0,
            tier="rejected",
            reasons=[
                "No recognized financial-statement section was found in this document "
                "(not the half-year filing's statement layout, nor the Information "
                "Document's summary table) -- likely not a financial statement at all."
            ],
        )

    score = 40.0
    reasons: List[str] = ["Recognized financial-statement section (40/40)."]

    if baseline_metrics.get("revenue") is not None:
        score += 30.0
        reasons.append("Revenue found via a deterministic table match (30/30).")
    elif merged_metrics.get("revenue") is not None:
        score += 15.0
        reasons.append("Revenue found only via AI narrative extraction, not a structured table match (15/30).")
    else:
        reasons.append("Revenue not found (0/30).")

    secondary_baseline = any(baseline_metrics.get(field) is not None for field in _SECONDARY_FIELDS)
    secondary_merged = any(merged_metrics.get(field) is not None for field in _SECONDARY_FIELDS)
    if secondary_baseline:
        score += 15.0
        reasons.append("At least one of cash/EBITDA/customers found via a deterministic table match (15/15).")
    elif secondary_merged:
        score += 8.0
        reasons.append("At least one of cash/EBITDA/customers found only via AI narrative extraction (8/15).")
    else:
        reasons.append("None of cash/EBITDA/customers found (0/15).")

    period_baseline = baseline_metrics.get("reporting_period") is not None or (
        baseline_metrics.get("reporting_period_start") is not None
        and baseline_metrics.get("reporting_period_end") is not None
    )
    period_merged = merged_metrics.get("reporting_period") is not None
    if period_baseline:
        score += 15.0
        reasons.append("Reporting period determined deterministically (15/15).")
    elif period_merged:
        score += 8.0
        reasons.append("Reporting period found only via AI narrative extraction (8/15).")
    else:
        reasons.append("Reporting period not determined (0/15).")

    tier = _tier_for(score)

    # A failed reconciliation caps the *tier*, not the score itself -- the
    # score stays an honest reflection of the point system above (useful as
    # a displayed "NN%"), while a numeric inconsistency is a separate,
    # independent red flag: every field could nominally be "found" and the
    # point total still be 100, while the actual numbers don't add up (a
    # strong signal of a misparse, e.g. a table-column shift). Matches
    # standard IDP practice: "flag the record regardless of confidence".
    if tier == "auto_accept" and (pnl_reconciles is False or cashflow_reconciles is False):
        failed = []
        if pnl_reconciles is False:
            failed.append("P&L (revenue - cost of sales does not equal gross profit)")
        if cashflow_reconciles is False:
            failed.append("cash flow (operating + investing + financing does not equal the net change in cash)")
        tier = "needs_review"
        reasons.append(
            f"Failed arithmetic reconciliation -- {', '.join(failed)} -- capped at 'needs_review' "
            "despite a full point score, since a numeric inconsistency suggests a misparse."
        )

    return ExtractionConfidence(score=round(score, 1), tier=tier, reasons=reasons)
