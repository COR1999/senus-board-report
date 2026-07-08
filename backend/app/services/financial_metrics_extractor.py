"""
FinancialMetricsExtractor (REWRITTEN)
======================================

Why this rewrite exists
-----------------------

The previous version of this extractor relied heavily on document-wide regular
expressions applied to raw OCR text extracted from PDFs.

This caused a critical class of errors:

1. Narrative leakage
   Example:
       "The Company expects to become EBITDA positive during FY2028"

   The old extractor incorrectly interpreted "2028" as EBITDA.

2. Context loss
   Financial reports contain multiple sections:
   - Chairman commentary
   - Strategy outlook
   - Risk disclosures
   - Financial statements (P&L, Balance Sheet, Cash Flow)

   Only the financial statements contain reliable numeric truth.

3. OCR structure is semi-tabular
   Extracted PDFs preserve line order but lose formatting. This means values
   appear on the next line rather than inline with labels.

This rewrite fixes those issues by:

- Locating financial statement sections first
- Parsing those sections line-by-line (not full-document regex)
- Treating tables as ordered row structures
- Ignoring narrative sections for financial metrics
- Only falling back to narrative when necessary

This makes the extractor significantly more reliable for real-world annual reports.

Public API
----------

    FinancialMetricsExtractor.extract(text: str) -> Dict[str, Any]

Returns (each field is `None` when not found in the document, as opposed
to a legitimate zero):

{
    "revenue": Optional[float], "revenue_prior": Optional[float],
    "cash": Optional[float], "cash_prior": Optional[float],
    "ebitda": Optional[float], "ebitda_prior": Optional[float],
    "customers": Optional[int],
    "bookings_value": Optional[float], "bookings_customers": Optional[int],
    "bookings_pipeline": Optional[float],
    "gross_margin": Optional[float], "gross_margin_prior": Optional[float],
    "operating_margin": Optional[float], "operating_margin_prior": Optional[float],
}

`bookings_value`/`bookings_customers`/`bookings_pipeline` are narrative-only
(same reliability class as `customers` -- not a structured table value),
e.g. "pipeline deals of approx. €700k across 21 enterprise customers
closed in the period (further approx. €500k of open pipeline)". No
`_prior` variants: this filing doesn't state a prior-period comparative
for bookings.

`ebitda`/`gross_margin`/`operating_margin` are now *computed* from
structured P&L/cash-flow lines (operating result + depreciation add-back,
gross profit / revenue, operating result / revenue) rather than searched
for as narrative text -- many real filings (including the one this was
built against) have no literal "EBITDA" line at all.

`_prior` fields are the same filing's own comparative-period column (most
half-year/annual reports print the prior period right next to the current
one, e.g. "Turnover 354,813 340,931") -- this lets YoY change be computed
from a single filing instead of only ever reading 0% until a second
document exists.

    FinancialMetricsExtractor.extract_balance_sheet(text: str) -> Dict[str, Any]

A second, independent method for the Cash & Liquidity / Solvency & Leverage
/ Returns fields that live on the separate BalanceSheetMetrics table (see
backend/docs/metrics-expansion-plan.md) -- these come from the balance
sheet and cash flow statement, not the P&L, and aren't part of `extract()`'s
original contract.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class FinancialMetricsExtractor:
    """
    Deterministic financial statement parser.
    No AI usage. Fully rule-based and structure-aware.
    """

    # =========================================================
    # SECTION DETECTION
    # =========================================================

    @staticmethod
    def _extract_section(text: str, start: str, end: Optional[str] = None) -> str:
        """
        Extracts a section of the document between two markers.
        Used to isolate P&L, Balance Sheet, Cash Flow.
        """
        if not text:
            return ""

        lower = text.lower()

        start_idx = lower.find(start.lower())
        if start_idx == -1:
            return ""

        end_idx = len(text)

        if end:
            end_idx_tmp = lower.find(end.lower(), start_idx)
            if end_idx_tmp != -1:
                end_idx = end_idx_tmp

        return text[start_idx:end_idx]

    @staticmethod
    def _clean_lines(section: str) -> List[str]:
        """
        Converts raw OCR block into clean line list.
        Removes empty noise lines.
        """
        if not section:
            return []

        lines = section.splitlines()
        return [l.strip() for l in lines if l and l.strip()]

    # =========================================================
    # NUMBER PARSING
    # =========================================================

    @staticmethod
    def _to_number(value: Optional[str]) -> float:
        """
        Converts strings like:
            "354,800"
            "354.8k"
            "1.2m"
            "2b"
            "-120k"
            "£354,813"
            "(120,000)"
        into float values.
        """

        if not value:
            return 0

        value = (
            value.strip()
            .lower()
            .replace(",", "")
            .replace("€", "")
            .replace("$", "")
            .replace("£", "")
        )

        # Financial statements commonly show negatives in parentheses
        # rather than with a leading minus sign, e.g. "(120,000)".
        negative = False
        if value.startswith("(") and value.endswith(")"):
            negative = True
            value = value[1:-1]

        multiplier = 1

        if value.endswith("k"):
            multiplier = 1_000
            value = value[:-1]
        elif value.endswith("m"):
            multiplier = 1_000_000
            value = value[:-1]
        elif value.endswith("b"):
            multiplier = 1_000_000_000
            value = value[:-1]

        try:
            result = float(value) * multiplier
            return -result if negative else result
        except ValueError:
            return 0

    # Matches financial-value tokens only: optional parens/currency/sign,
    # a leading digit, then any run of digits/commas, optional decimal,
    # optional k/m/b magnitude suffix. Anything with letters outside that
    # suffix position (e.g. "FY2028", "EBITDA") cannot match because the
    # pattern is fully anchored (^...$) — there is no room for stray text.
    _NUMBER_RE = re.compile(r"^\(?[€$£]?-?\d[\d,]*\.?\d*[kKmMbB]?\)?$")

    @classmethod
    def _is_number(cls, token: Optional[str]) -> bool:
        """
        Returns True if `token` looks like a financial numeric value
        (e.g. "354,813", "354.8k", "1.2m", "-120,000", "€354,813",
        "$1.2m", "(120,000)").

        Returns False for labels, units, and narrative tokens
        (e.g. "Turnover", "EBITDA", "%", "FY2028", "positive", "growth").

        This is a token-shape check only. It does not know about years vs.
        values semantically — that distinction is enforced upstream by
        restricting parsing to isolated financial-statement sections, so a
        bare "2028" inside a P&L row is treated as a legitimate figure.
        """
        if not token:
            return False

        token = token.strip()
        if not token:
            return False

        if not cls._NUMBER_RE.match(token):
            return False

        return any(c.isdigit() for c in token)

    @staticmethod
    def _find_first(patterns: List[str], text: str) -> Optional[str]:
        """
        Regex fallback helper (only used when structured parsing fails).
        """
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1)
        return None

    # =========================================================
    # SECTION FINDERS
    # =========================================================

    @classmethod
    def _get_pnl(cls, text: str) -> str:
        return cls._extract_section(
            text,
            "consolidated profit and loss",
            "balance sheet"
        )

    @classmethod
    def _get_balance_sheet(cls, text: str) -> str:
        return cls._extract_section(
            text,
            "consolidated balance sheet",
            "cash flow"
        )

    @classmethod
    def _get_cashflow(cls, text: str) -> str:
        return cls._extract_section(
            text,
            "cash flow"
        )

    @classmethod
    def extract_statement_text(cls, text: str, max_chars: int = 8000) -> str:
        """
        Public helper for callers (e.g. the AI enrichment layer) that need
        a compact, statement-only view of the document instead of raw
        text. Reuses the same section isolation as `extract()` so the
        AI layer sees the P&L / balance sheet / cash flow tables rather
        than cover pages, TOCs, or narrative commentary -- smaller prompt,
        less chance the real tables get truncated out.

        Falls back to the first `max_chars` of raw text when no statement
        markers are found (e.g. a non-standard report layout).
        """
        if not text:
            return ""

        sections = [
            cls._get_pnl(text),
            cls._get_balance_sheet(text),
            cls._get_cashflow(text),
        ]

        combined = "\n\n".join(s for s in sections if s).strip()

        if not combined:
            combined = text

        return combined[:max_chars]

    # =========================================================
    # TABLE / LINE PARSING CORE
    # =========================================================

    @classmethod
    def _find_value_next_line(cls, lines: List[str], keyword: str) -> Optional[str]:
        """
        Financial statements are often OCR'd as:

            Turnover
            354,813

        or, when a prior-year comparison column is present:

            Turnover
            354,813   340,931

        This helper returns the first numeric token on the line after a
        label (the current-period column). Returning the raw, unsplit
        next line here would make downstream parsing silently fail on
        any two-column row, since "354,813 340,931" isn't parseable as
        a single number.
        """
        for i, line in enumerate(lines):
            if keyword in line.lower():
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    for token in next_line.split():
                        if cls._is_number(token):
                            return token
        return None

    @classmethod
    def _find_value_same_line(cls, lines: List[str], keyword: str) -> Optional[str]:
        """
        Handles cases like:
            Turnover 354,813
        """
        for line in lines:
            if keyword in line.lower():
                parts = line.split()
                for p in parts:
                    if cls._is_number(p):
                        return p
        return None

    @classmethod
    def _extract_table_value(cls, lines: List[str], keyword: str) -> Optional[str]:
        """
        Try structured table extraction first, then fallback.
        """
        return (
            cls._find_value_next_line(lines, keyword)
            or cls._find_value_same_line(lines, keyword)
        )

    @classmethod
    def _find_pair_next_lines(cls, lines: List[str], keyword: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Same idea as `_find_value_next_line`, but also captures the prior-
        period comparative. This PDF's extraction lays each column out on
        its own line:

            Turnover
            354,813
            340,931

        so the current-period value is the first numeric token found after
        the label line, and the prior-period value is the first numeric
        token found after *that*. Returns (None, None) if the label isn't
        found at all, or (current, None) if a prior-period token isn't
        found (e.g. no comparative column in this filing).
        """
        # Bounded lookahead (not an unbounded forward scan): a label can
        # itself wrap onto a second line (e.g. "...more than one" / "year"),
        # so the current/prior values don't always start at exactly i+1/i+2.
        # Capped at 4 lines so a single-column filing with no comparative
        # doesn't walk into a later, unrelated row's value.
        _MAX_LOOKAHEAD = 4

        for i, line in enumerate(lines):
            if keyword not in line.lower():
                continue

            found: List[str] = []
            for line_ahead in lines[i + 1 : i + 1 + _MAX_LOOKAHEAD]:
                for token in line_ahead.split():
                    if cls._is_number(token):
                        found.append(token)
                if len(found) >= 2:
                    break

            current = found[0] if len(found) > 0 else None
            prior = found[1] if len(found) > 1 else None
            return current, prior
        return None, None

    @classmethod
    def _find_pair_same_line(cls, lines: List[str], keyword: str) -> Tuple[Optional[str], Optional[str]]:
        """Handles "Turnover 354,813 340,931" all on one line."""
        for line in lines:
            if keyword in line.lower():
                tokens = [t for t in line.split() if cls._is_number(t)]
                current = tokens[0] if len(tokens) > 0 else None
                prior = tokens[1] if len(tokens) > 1 else None
                return current, prior
        return None, None

    @classmethod
    def _extract_table_pair(cls, lines: List[str], keyword: str) -> Tuple[Optional[str], Optional[str]]:
        current, prior = cls._find_pair_next_lines(lines, keyword)
        if current is None:
            current, prior = cls._find_pair_same_line(lines, keyword)
        return current, prior

    @classmethod
    def _to_number_or_none(cls, raw: Optional[str]) -> Optional[float]:
        return cls._to_number(raw) if raw is not None else None

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

    # =========================================================
    # SHARED EXTRACTION CORE
    # =========================================================

    # Every key `_extract_all`/`_extract_all_information_document` must
    # return, defaulted to `None` -- the Information Document path fills in
    # a small subset (see its own docstring for exactly which, and why the
    # rest genuinely aren't disclosed by that document type) and returns
    # this dict with those few keys overridden, rather than duplicating the
    # full key list in two places.
    _ALL_FIELDS_DEFAULT: Dict[str, Any] = {
        "revenue": None, "revenue_prior": None,
        "cash": None, "cash_prior": None,
        "ebitda": None, "ebitda_prior": None,
        "customers": None,
        "bookings_value": None, "bookings_customers": None, "bookings_pipeline": None,
        "reporting_period": None, "reporting_period_prior": None,
        "reporting_period_end": None, "reporting_period_end_prior": None,
        "reporting_period_start": None, "reporting_period_start_prior": None,
        "gross_margin": None, "gross_margin_prior": None,
        "operating_margin": None, "operating_margin_prior": None,
        "total_debt": None, "total_debt_prior": None,
        "interest_expense": None, "interest_expense_prior": None,
        "cost_of_sales": None, "cost_of_sales_prior": None,
        "administrative_expenses": None, "administrative_expenses_prior": None,
        "working_capital_change": None, "working_capital_change_prior": None,
        "capital_employed": None, "capital_employed_prior": None,
        "net_cash_used_operating": None, "net_cash_used_operating_prior": None,
        "operating_result": None, "operating_result_prior": None,
    }

    @classmethod
    def _extract_all_information_document(cls, text: str) -> Dict[str, Any]:
        """
        Extraction path for Senus's "Information Document" (IPO/listing
        prospectus) format -- see `_get_information_document_summary`'s
        docstring for why this is structurally different from the
        half-year filing. Only what's genuinely in that one summary table
        is filled in; everything else stays `None` (never guessed) --
        notably `ebitda`/`interest_expense`/`capital_employed`/
        `total_debt`/`working_capital_change`/`net_cash_used_operating`,
        since no depreciation, interest, or balance-sheet-subtotal figures
        are disclosed anywhere in this document (confirmed by direct
        inspection of the real filing, not assumed).
        """
        summary_lines = cls._clean_lines(cls._get_information_document_summary(text))

        revenue_raw, revenue_prior_raw = cls._extract_table_pair(summary_lines, "turnover")
        gross_profit_raw, gross_profit_prior_raw = cls._extract_table_pair(summary_lines, "gross profit")

        # Unlike the half-year filing's "group operating loss"/"group
        # operating profit" (two labels, sign implied by which one
        # matched), this table uses one label ("Operating Profit / (Loss)")
        # with the sign already embedded in the printed value itself via
        # parentheses (e.g. "(633,694)") -- `_to_number` already handles
        # parenthesized negatives, so no separate sign-flip is needed here.
        operating_result_raw, operating_result_prior_raw = cls._extract_table_pair(
            summary_lines, "operating profit / (loss)"
        )

        # Not the bare "cash and cash equivalents" substring -- this table
        # has both a beginning-of-year and end-of-year row under that same
        # substring, and the bare match would hit the beginning-of-year row
        # first (wrong -- the ending balance is the point-in-time figure
        # that belongs on the dashboard, matching the half-year filing's
        # own balance-sheet convention).
        cash_raw, cash_prior_raw = cls._extract_table_pair(
            summary_lines, "cash and cash equivalents at end of financial year"
        )

        # Customers: this document's own phrasing ("provided its solution
        # to 36 Enterprise customers...") differs from the half-year
        # filing's ("serving 138 customers") -- tried first, falling back
        # to the generic patterns in case a future filing uses either.
        customers_raw = cls._find_first([
            r"provided\s+its\s+solution\s+to\s+(\d[\d,]*)\s+Enterprise\s+customers",
            r"serving\s+(\d[\d,]*)\s+customer",
            r"(\d[\d,]*)\s+customers?",
        ], text)

        period_fields = cls._extract_period_fields(text)

        revenue = cls._to_number_or_none(revenue_raw)
        revenue_prior = cls._to_number_or_none(revenue_prior_raw)
        gross_profit = cls._to_number_or_none(gross_profit_raw)
        gross_profit_prior = cls._to_number_or_none(gross_profit_prior_raw)
        operating_result = cls._to_number_or_none(operating_result_raw)
        operating_result_prior = cls._to_number_or_none(operating_result_prior_raw)
        cash = cls._to_number_or_none(cash_raw)
        cash_prior = cls._to_number_or_none(cash_prior_raw)
        customers = int(customers_raw.replace(",", "")) if customers_raw else None

        gross_margin = (
            gross_profit / revenue * 100 if gross_profit is not None and revenue else None
        )
        gross_margin_prior = (
            gross_profit_prior / revenue_prior * 100
            if gross_profit_prior is not None and revenue_prior
            else None
        )
        operating_margin = (
            operating_result / revenue * 100 if operating_result is not None and revenue else None
        )
        operating_margin_prior = (
            operating_result_prior / revenue_prior * 100
            if operating_result_prior is not None and revenue_prior
            else None
        )

        fields = dict(cls._ALL_FIELDS_DEFAULT)
        fields.update({
            "revenue": revenue,
            "revenue_prior": revenue_prior,
            "cash": cash,
            "cash_prior": cash_prior,
            "customers": customers,
            "gross_margin": gross_margin,
            "gross_margin_prior": gross_margin_prior,
            "operating_margin": operating_margin,
            "operating_margin_prior": operating_margin_prior,
            "operating_result": operating_result,
            "operating_result_prior": operating_result_prior,
            **period_fields,
        })
        return fields

    @classmethod
    def _extract_all(cls, text: str) -> Dict[str, Any]:
        """
        Parses every field `extract()` and `extract_balance_sheet()` need,
        once, so both public methods can pull their own subset of keys
        without re-running section isolation/table parsing twice.

        Dispatches by document format: the half-year filing's three-
        statement layout (`consolidated profit and loss` marker) is tried
        first, since it's the format this method has always parsed;
        falls back to the Information Document's single-summary-table
        format when the half-year marker isn't found but the Information
        Document's is. A document matching neither format (e.g. a
        governance PDF) falls through to the code below, where every table
        lookup simply fails to match and every field stays `None` --
        unchanged behavior from before this dispatch existed.
        """
        if not text:
            text = ""

        if not cls._get_pnl(text) and cls._get_information_document_summary(text):
            return cls._extract_all_information_document(text)

        pnl = cls._get_pnl(text)
        balance = cls._get_balance_sheet(text)
        cashflow = cls._get_cashflow(text)

        pnl_lines = cls._clean_lines(pnl)
        balance_lines = cls._clean_lines(balance)
        cashflow_lines = cls._clean_lines(cashflow)

        # --- Revenue (turnover first -- most reliable label) ---
        revenue_raw, revenue_prior_raw = cls._extract_table_pair(pnl_lines, "turnover")
        if revenue_raw is None:
            revenue_raw, revenue_prior_raw = cls._extract_table_pair(pnl_lines, "revenue")

        # --- Cash (balance sheet only) ---
        cash_raw, cash_prior_raw = cls._extract_table_pair(balance_lines, "cash and cash equivalents")

        # --- P&L lines feeding computed EBITDA/margins and Solvency/Returns ---
        cost_of_sales_raw, cost_of_sales_prior_raw = cls._extract_table_pair(pnl_lines, "cost of sales")
        gross_profit_raw, gross_profit_prior_raw = cls._extract_table_pair(pnl_lines, "gross profit")
        admin_raw, admin_prior_raw = cls._extract_table_pair(pnl_lines, "administrative expenses")
        interest_raw, interest_prior_raw = cls._extract_table_pair(pnl_lines, "interest payable")

        # Operating result: label varies with sign (loss vs profit). Whichever
        # label matches determines the sign -- a "profit" row is a positive
        # contribution, a "loss" row is negative (matching how this business's
        # actual filing prints a loss as a plain positive magnitude on its own
        # row, with "loss"/"profit" only distinguished by the label text, not
        # a minus sign).
        operating_result_raw, operating_result_prior_raw = cls._extract_table_pair(pnl_lines, "group operating loss")
        operating_is_loss = operating_result_raw is not None
        if operating_result_raw is None:
            operating_result_raw, operating_result_prior_raw = cls._extract_table_pair(pnl_lines, "group operating profit")

        # --- Cash flow statement lines ---
        depreciation_raw, depreciation_prior_raw = cls._extract_table_pair(cashflow_lines, "depreciation")
        working_capital_raw, working_capital_prior_raw = cls._extract_table_pair(cashflow_lines, "movements in working capital")
        net_cash_operating_raw, net_cash_operating_prior_raw = cls._extract_table_pair(
            cashflow_lines, "net cash used in operating activities"
        )

        # --- Balance sheet lines (Solvency & Returns) ---
        # Bank debt is only reliably structured under this label in this
        # filing's balance sheet (the narrative "Cash and bank debt balances
        # were €735.1k and €76.5k respectively" sentence is a fragile
        # two-values-in-one-sentence fallback we don't need here). Matched
        # on a substring that stays on one OCR'd line -- the full label
        # ("...more than one year") wraps across two lines in this filing,
        # so matching the full phrase would never hit.
        debt_raw, debt_prior_raw = cls._extract_table_pair(
            balance_lines, "amounts falling due after more than one"
        )
        capital_employed_raw, capital_employed_prior_raw = cls._extract_table_pair(
            balance_lines, "total assets less current liabilities"
        )

        # --- Customers (narrative + table safe, no prior column exists) ---
        customers_raw = cls._find_first([
            r"serving\s+(\d[\d,]*)\s+customer",
            r"(\d[\d,]*)\s+customers?",
        ], text)

        # --- Bookings (narrative only -- same reliability class as
        # customers above, not a structured table value). e.g. "pipeline
        # deals of approx. €700k across 21 enterprise customers closed in
        # the period (further approx. €500k of open pipeline)". \s+ (not a
        # literal space) between words since this filing's OCR text wraps
        # mid-sentence with real newlines. ---
        bookings_match = re.search(
            r"pipeline\s+deals\s+of\s+approx\.?\s*[€$£]?([\d,.]+\s*[kKmMbB]?)"
            r"\s+across\s+(\d+)\s+enterprise\s+customers\s+closed",
            text, re.IGNORECASE,
        )
        bookings_value_raw = bookings_match.group(1) if bookings_match else None
        bookings_customers_raw = bookings_match.group(2) if bookings_match else None

        bookings_pipeline_raw = cls._find_first([
            r"further\s+approx\.?\s*[€$£]?([\d,.]+\s*[kKmMbB]?)\s+of\s+open\s+pipeline",
        ], text)

        period_fields = cls._extract_period_fields(text)
        reporting_period = period_fields["reporting_period"]
        reporting_period_prior = period_fields["reporting_period_prior"]
        reporting_period_end = period_fields["reporting_period_end"]
        reporting_period_end_prior = period_fields["reporting_period_end_prior"]
        reporting_period_start = period_fields["reporting_period_start"]
        reporting_period_start_prior = period_fields["reporting_period_start_prior"]

        # -----------------------------------------------------
        # NORMALISE
        # -----------------------------------------------------
        revenue = cls._to_number_or_none(revenue_raw)
        revenue_prior = cls._to_number_or_none(revenue_prior_raw)
        cash = cls._to_number_or_none(cash_raw)
        cash_prior = cls._to_number_or_none(cash_prior_raw)
        cost_of_sales = cls._to_number_or_none(cost_of_sales_raw)
        cost_of_sales_prior = cls._to_number_or_none(cost_of_sales_prior_raw)
        gross_profit = cls._to_number_or_none(gross_profit_raw)
        gross_profit_prior = cls._to_number_or_none(gross_profit_prior_raw)
        administrative_expenses = cls._to_number_or_none(admin_raw)
        administrative_expenses_prior = cls._to_number_or_none(admin_prior_raw)
        interest_expense = cls._to_number_or_none(interest_raw)
        interest_expense_prior = cls._to_number_or_none(interest_prior_raw)
        depreciation = cls._to_number_or_none(depreciation_raw)
        depreciation_prior = cls._to_number_or_none(depreciation_prior_raw)
        working_capital_change = cls._to_number_or_none(working_capital_raw)
        working_capital_change_prior = cls._to_number_or_none(working_capital_prior_raw)
        capital_employed = cls._to_number_or_none(capital_employed_raw)
        capital_employed_prior = cls._to_number_or_none(capital_employed_prior_raw)
        customers = int(customers_raw.replace(",", "")) if customers_raw else None
        bookings_value = cls._to_number_or_none(bookings_value_raw)
        bookings_customers = int(bookings_customers_raw) if bookings_customers_raw else None
        bookings_pipeline = cls._to_number_or_none(bookings_pipeline_raw)

        # net_cash_used_operating and total_debt are stored as positive
        # magnitudes (this filing prints them as negative/liability figures
        # -- "cash used" and "debt owed" read more naturally as magnitudes
        # for burn-rate division and net-debt subtraction respectively).
        net_cash_used_operating = cls._to_number_or_none(net_cash_operating_raw)
        if net_cash_used_operating is not None:
            net_cash_used_operating = abs(net_cash_used_operating)
        net_cash_used_operating_prior = cls._to_number_or_none(net_cash_operating_prior_raw)
        if net_cash_used_operating_prior is not None:
            net_cash_used_operating_prior = abs(net_cash_used_operating_prior)

        total_debt = cls._to_number_or_none(debt_raw)
        if total_debt is not None:
            total_debt = abs(total_debt)
        total_debt_prior = cls._to_number_or_none(debt_prior_raw)
        if total_debt_prior is not None:
            total_debt_prior = abs(total_debt_prior)

        operating_result = cls._to_number_or_none(operating_result_raw)
        if operating_result is not None and operating_is_loss:
            operating_result = -operating_result
        operating_result_prior = cls._to_number_or_none(operating_result_prior_raw)
        if operating_result_prior is not None and operating_is_loss:
            operating_result_prior = -operating_result_prior

        # EBITDA = operating result (EBIT) + depreciation/amortisation
        # add-back. There is no literal "EBITDA" line in this filing (or
        # many real filings) -- this reconciles the same way the cash flow
        # statement's own "Adjustments for:" section does (loss + interest
        # + depreciation), just starting from EBIT instead of loss-after-interest
        # so interest doesn't need to be added back separately.
        ebitda = (
            operating_result + depreciation
            if operating_result is not None and depreciation is not None
            else None
        )
        ebitda_prior = (
            operating_result_prior + depreciation_prior
            if operating_result_prior is not None and depreciation_prior is not None
            else None
        )

        gross_margin = (
            gross_profit / revenue * 100
            if gross_profit is not None and revenue
            else None
        )
        gross_margin_prior = (
            gross_profit_prior / revenue_prior * 100
            if gross_profit_prior is not None and revenue_prior
            else None
        )
        operating_margin = (
            operating_result / revenue * 100
            if operating_result is not None and revenue
            else None
        )
        operating_margin_prior = (
            operating_result_prior / revenue_prior * 100
            if operating_result_prior is not None and revenue_prior
            else None
        )

        return {
            "revenue": revenue,
            "revenue_prior": revenue_prior,
            "cash": cash,
            "cash_prior": cash_prior,
            "ebitda": ebitda,
            "ebitda_prior": ebitda_prior,
            "customers": customers,
            "bookings_value": bookings_value,
            "bookings_customers": bookings_customers,
            "bookings_pipeline": bookings_pipeline,
            "reporting_period": reporting_period,
            "reporting_period_prior": reporting_period_prior,
            "reporting_period_end": reporting_period_end,
            "reporting_period_end_prior": reporting_period_end_prior,
            "reporting_period_start": reporting_period_start,
            "reporting_period_start_prior": reporting_period_start_prior,
            "gross_margin": gross_margin,
            "gross_margin_prior": gross_margin_prior,
            "operating_margin": operating_margin,
            "operating_margin_prior": operating_margin_prior,
            "total_debt": total_debt,
            "total_debt_prior": total_debt_prior,
            "interest_expense": interest_expense,
            "interest_expense_prior": interest_expense_prior,
            "cost_of_sales": cost_of_sales,
            "cost_of_sales_prior": cost_of_sales_prior,
            "administrative_expenses": administrative_expenses,
            "administrative_expenses_prior": administrative_expenses_prior,
            "working_capital_change": working_capital_change,
            "working_capital_change_prior": working_capital_change_prior,
            "capital_employed": capital_employed,
            "capital_employed_prior": capital_employed_prior,
            "net_cash_used_operating": net_cash_used_operating,
            "net_cash_used_operating_prior": net_cash_used_operating_prior,
            "operating_result": operating_result,
            "operating_result_prior": operating_result_prior,
        }

    # =========================================================
    # PUBLIC API
    # =========================================================

    @classmethod
    def extract(cls, text: str) -> Dict[str, Any]:
        all_fields = cls._extract_all(text)
        return {
            key: all_fields[key]
            for key in (
                "revenue", "revenue_prior",
                "cash", "cash_prior",
                "ebitda", "ebitda_prior",
                "customers",
                "bookings_value", "bookings_customers", "bookings_pipeline",
                "reporting_period", "reporting_period_prior",
                "reporting_period_end", "reporting_period_end_prior",
                "reporting_period_start", "reporting_period_start_prior",
                "gross_margin", "gross_margin_prior",
                "operating_margin", "operating_margin_prior",
            )
        }

    @classmethod
    def extract_balance_sheet(cls, text: str) -> Dict[str, Any]:
        all_fields = cls._extract_all(text)
        return {
            key: all_fields[key]
            for key in (
                "total_debt", "total_debt_prior",
                "interest_expense", "interest_expense_prior",
                "cost_of_sales", "cost_of_sales_prior",
                "administrative_expenses", "administrative_expenses_prior",
                "working_capital_change", "working_capital_change_prior",
                "capital_employed", "capital_employed_prior",
                "net_cash_used_operating", "net_cash_used_operating_prior",
                "operating_result", "operating_result_prior",
            )
        }

    # Reconciliation tolerance -- financial statements sometimes round
    # individual lines to the nearest unit independently, so component
    # sums can be off by a euro or two from the stated total without that
    # being a real misparse. Anything beyond this is a genuine mismatch.
    _RECONCILIATION_TOLERANCE = 2.0

    @classmethod
    def check_reconciliation(cls, text: str) -> Dict[str, Optional[bool]]:
        """
        Deterministic arithmetic sanity checks, independent of which
        document format matched -- this project's equivalent of "Subtotal
        + Tax = Total" for an invoice. Catches a genuine misparse (e.g. a
        table-column shift silently matching the wrong number to a label)
        that field-presence checks alone can't: all the involved fields
        would still show as "found", just wrong.

        Returns `None` for either check (not `False`) when the document
        doesn't disclose enough of the relevant figures to check it at all
        -- "we couldn't verify this" is a different, weaker signal than "we
        verified it and it's wrong", and conflating the two would either
        wrongly penalize a legitimately sparser filing (see the Information
        Document, which has no `cost_of_sales` line at all) or wrongly wave
        through a real mismatch as if it had been checked.
        """
        pnl_lines = cls._clean_lines(cls._get_pnl(text))
        if not pnl_lines:
            pnl_lines = cls._clean_lines(cls._get_information_document_summary(text))

        revenue_raw, _ = cls._extract_table_pair(pnl_lines, "turnover")
        if revenue_raw is None:
            revenue_raw, _ = cls._extract_table_pair(pnl_lines, "revenue")
        cost_of_sales_raw, _ = cls._extract_table_pair(pnl_lines, "cost of sales")
        gross_profit_raw, _ = cls._extract_table_pair(pnl_lines, "gross profit")

        revenue = cls._to_number_or_none(revenue_raw)
        cost_of_sales = cls._to_number_or_none(cost_of_sales_raw)
        gross_profit = cls._to_number_or_none(gross_profit_raw)

        pnl_reconciles: Optional[bool] = None
        if revenue is not None and cost_of_sales is not None and gross_profit is not None:
            pnl_reconciles = abs((revenue - cost_of_sales) - gross_profit) <= cls._RECONCILIATION_TOLERANCE

        # Cash flow: both formats print the same standard structure
        # ("Cash flows from Operating/Investing/Financing Activities", a
        # beginning balance, an ending balance) with identical labels --
        # checked against the *whole* document rather than an isolated
        # section, since the half-year filing's cash-flow lines sit inside
        # its single "cash flow" section but the Information Document's
        # sit inside its "summary financial information" table; scanning
        # the full text for these specific, unambiguous labels works for
        # both without needing per-format section isolation here too.
        cashflow_lines = cls._clean_lines(text)
        operating_raw, _ = cls._extract_table_pair(cashflow_lines, "cash flows from operating activities")
        investing_raw, _ = cls._extract_table_pair(cashflow_lines, "cash flows from investing activities")
        financing_raw, _ = cls._extract_table_pair(cashflow_lines, "cash flows from financing activities")
        opening_cash_raw, _ = cls._extract_table_pair(cashflow_lines, "at beginning")
        closing_cash_raw, _ = cls._extract_table_pair(cashflow_lines, "at end of")

        operating_cf = cls._to_number_or_none(operating_raw)
        investing_cf = cls._to_number_or_none(investing_raw)
        financing_cf = cls._to_number_or_none(financing_raw)
        opening_cash = cls._to_number_or_none(opening_cash_raw)
        closing_cash = cls._to_number_or_none(closing_cash_raw)

        cashflow_reconciles: Optional[bool] = None
        if None not in (operating_cf, investing_cf, financing_cf, opening_cash, closing_cash):
            net_change = closing_cash - opening_cash
            cashflow_reconciles = (
                abs((operating_cf + investing_cf + financing_cf) - net_change)
                <= cls._RECONCILIATION_TOLERANCE
            )

        return {"pnl_reconciles": pnl_reconciles, "cashflow_reconciles": cashflow_reconciles}
