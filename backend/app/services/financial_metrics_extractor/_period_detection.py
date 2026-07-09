"""
Reporting-period/cadence detection and document-format recognition --
shared by every extraction path in `_field_extraction.py`, independent of
which document format actually matched.
"""

import re
from typing import Dict, Optional

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class PeriodDetectionMixin:
    """Requires `TextParsingMixin` to also be mixed in (uses `_extract_section`/`_get_pnl`)."""

    # =========================================================
    # PERIOD / CADENCE (shared by every document format)
    # =========================================================

    @classmethod
    def _extract_period_fields(cls, text: str) -> Dict[str, Optional[str]]:
        """
        Reporting-period detection, shared by every document format this
        extractor supports (narrative-only, same reliability class as
        customers/bookings). Two independent signals:

        1. A literal `(HYxx)`/`(HYxx: ...)` label, when the filing states
           its own period that way (the half-year filing does; the
           Information Document never does -- it has no "(HYxx)"/"(FYxx)"
           notation at all, just repeated prose like "financial year ended
           30 June 2025").
        2. A generic "ended DD Month YYYY" date, present in both formats,
           plus a cadence cue (half-year vs. full-year phrasing) to derive
           the period's start date and, when no literal HY/FY label exists,
           an "FY{year}" label for a full-year filing.
        """
        def _four_digit_year(digits: str) -> str:
            # A 2-digit year always means 20xx for a company that didn't
            # exist last century -- safe, unambiguous expansion, not a guess.
            return f"20{digits}" if len(digits) == 2 else digits

        reporting_period_match = re.search(r"\(HY(\d{2,4})\)", text)
        reporting_period = (
            f"HY{_four_digit_year(reporting_period_match.group(1))}" if reporting_period_match else None
        )

        reporting_period_prior_match = re.search(r"\(HY(\d{2,4}):", text)
        reporting_period_prior = (
            f"HY{_four_digit_year(reporting_period_prior_match.group(1))}" if reporting_period_prior_match else None
        )

        # --- Reporting period end date, e.g. "Dec 2025" (a clearer axis
        # label than the bare "HY2026", which doesn't say which calendar
        # month the period actually ends -- Senus's fiscal year runs
        # Jul-Jun, so "HY2026" ends in December, not June, and real
        # stakeholders found the HY-only label ambiguous). The filing
        # states this once per financial statement section, e.g. "for the
        # six months ended 31 December 2025" -- there's no separate literal
        # date for the *prior* period anywhere in the text (only the prior
        # period's numeric column, no header), so the prior label is
        # derived as the same month one year earlier, which is safe here
        # because both half-year and full-year filings compare like-for-like
        # periods a year apart, not an arbitrary guess.
        period_end_match = re.search(
            r"ended\s+(\d{1,2})\s+(January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+(\d{4})",
            text, re.IGNORECASE,
        )
        reporting_period_end = None
        reporting_period_end_prior = None
        reporting_period_start = None
        reporting_period_start_prior = None
        if period_end_match:
            month_name = period_end_match.group(2).capitalize()
            year = int(period_end_match.group(3))
            reporting_period_end = f"{month_name[:3]} {year}"
            reporting_period_end_prior = f"{month_name[:3]} {year - 1}"

            # Period start, e.g. "Jul 2025" -- N-1 months before the end
            # month, where N is the filing's own reporting cadence in
            # months. The "ended DD Month YYYY" match above says nothing
            # about cadence (it matches "twelve months ended" just as well
            # as "six months ended"), so a hardcoded half-year assumption
            # here would silently mislabel a full-year filing's start date
            # by 6 months. Cadence is instead detected from the filing's
            # own language; when neither a half-year nor a full-year cue is
            # found, cadence is genuinely ambiguous and the start fields
            # are left None rather than guessed -- same missing-vs-
            # fabricated discipline as every other field in this extractor
            # (bookings, customers, reporting_period all do the same).
            # Year rollover is handled manually since there's no
            # python-dateutil dependency in this project.
            #
            # Searched in a bounded window around the period-end match
            # itself, not the whole document -- confirmed against the real
            # Information Document that scanning the full text produces a
            # real false positive: a forward-looking sentence 40+ pages
            # away ("a trading update following completion of the half
            # year ending 31 December 2025") matched `half_year_cues`
            # despite this being an annual (FY2025) filing, making the
            # cadence look ambiguous when it plainly isn't near the actual
            # period statement. This is the same narrative-leakage failure
            # mode this whole extractor was rewritten to avoid, just
            # surfacing in a cue regex instead of a value regex.
            _CADENCE_CUE_WINDOW = 200
            cue_window = text[
                max(0, period_end_match.start() - _CADENCE_CUE_WINDOW) : period_end_match.end() + _CADENCE_CUE_WINDOW
            ]
            half_year_cues = re.search(
                r"\bsix\s+months\s+ended\b|\bhalf[\s-]year\b|\(HY\d", cue_window, re.IGNORECASE
            )
            # Broadened beyond the half-year filing's own phrasing to also
            # match the Information Document's real, confirmed phrasings --
            # "twelve months to 30 June 2025", "financial year ended 30 June
            # 2025", "12-month period ended 30 June 2025" -- none of which
            # the original (narrower) alternatives matched at all.
            full_year_cues = re.search(
                r"\btwelve\s+months\s+ended\b|\btwelve\s+months\s+to\b|\b12\s+months\s+ended\b|"
                r"\b12-month\s+period\s+ended\b|\bfinancial\s+year\s+ended\b|\bfull\s+year\b|"
                r"\bannual\s+report\b|\(FY\d",
                cue_window, re.IGNORECASE,
            )
            period_months = (
                6 if half_year_cues and not full_year_cues else
                12 if full_year_cues and not half_year_cues else
                None
            )
            if period_months is not None:
                start_offset = period_months - 1
                end_index = _MONTH_ABBR.index(month_name[:3])
                start_index = (end_index - start_offset) % 12
                start_year = year - 1 if end_index - start_offset < 0 else year
                reporting_period_start = f"{_MONTH_ABBR[start_index]} {start_year}"
                reporting_period_start_prior = f"{_MONTH_ABBR[start_index]} {start_year - 1}"

            # No literal "(HYxx)"/"(FYxx)" label anywhere (the Information
            # Document's case) but a full-year cadence was detected from
            # the filing's own language -- derive an "FYyyyy" label from
            # the same year already used for `reporting_period_end`, rather
            # than leaving a full-year filing with no period label at all.
            if reporting_period is None and period_months == 12:
                reporting_period = f"FY{year}"
                reporting_period_prior = f"FY{year - 1}"

        return {
            "reporting_period": reporting_period,
            "reporting_period_prior": reporting_period_prior,
            "reporting_period_end": reporting_period_end,
            "reporting_period_end_prior": reporting_period_end_prior,
            "reporting_period_start": reporting_period_start,
            "reporting_period_start_prior": reporting_period_start_prior,
        }

    # =========================================================
    # DOCUMENT FORMAT DETECTION
    # =========================================================

    @classmethod
    def _get_information_document_summary(cls, text: str) -> str:
        """
        Isolates the Information Document's one financial table -- an
        IPO/listing prospectus format, structurally unrelated to the
        half-year filing's three separately-headed statements (see
        backend/docs/source-documents/README.md). This document states
        once that its real full accounts are a separate, appended (and
        separately unparseable, scanned) filing -- this summary table is
        genuinely all the structured data this format has.

        Bounded to end at the "Profit and Loss" narrative subheading that
        immediately follows the table (not the later "Bankruptcy,
        Liquidation..." heading, tried first and found too wide): the real
        document has narrative commentary between the table and that
        later heading -- e.g. "...reflecting improved operational
        efficiency and reductions in cost of sales" -- containing prose
        sentences with their own numbers. `_extract_table_pair`'s keyword
        matching doesn't distinguish a real table row from a narrative
        sentence that happens to contain the same words, so including that
        commentary in the isolated section previously matched "cost of
        sales" against a sentence about administrative expenses instead of
        the table (which has no cost-of-sales row at all) -- exactly the
        narrative-leakage failure mode this extractor was rewritten to
        avoid (see this file's module docstring). Confirmed by testing
        against the real document, not assumed.
        """
        return cls._extract_section(text, "summary financial information", "profit and loss")

    @classmethod
    def is_format_recognized(cls, text: str) -> bool:
        """
        True when this document matches a format this extractor actually
        knows how to parse -- the half-year filing's three-statement
        layout, or the Information Document's single summary table. A
        document matching neither (e.g. an AGM notice, a Memorandum &
        Articles of Association) returns False here, which the extraction
        confidence service (`extraction_confidence.py`) uses to cap
        confidence at 0 regardless of any narrative-regex "hits" elsewhere
        in the text -- an unrecognized format's other matches are more
        likely coincidental noise than real data.
        """
        return bool(cls._get_pnl(text)) or bool(cls._get_information_document_summary(text))
