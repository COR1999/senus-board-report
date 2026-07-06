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

Public API (UNCHANGED)
----------------------

    FinancialMetricsExtractor.extract(text: str) -> Dict[str, Any]

Returns (each field is `None` when not found in the document, as opposed
to a legitimate zero):

{
    "revenue": Optional[float],
    "cash": Optional[float],
    "ebitda": Optional[float],
    "customers": Optional[int],
    "gross_margin": Optional[float],
    "operating_margin": Optional[float]
}
"""

import re
from typing import Dict, Any, List, Optional


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

    # =========================================================
    # MAIN EXTRACTION
    # =========================================================

    @classmethod
    def extract(cls, text: str) -> Dict[str, Any]:

        if not text:
            text = ""

        # -----------------------------------------------------
        # 1. SPLIT INTO STRUCTURED SECTIONS
        # -----------------------------------------------------

        pnl = cls._get_pnl(text)
        balance = cls._get_balance_sheet(text)
        cashflow = cls._get_cashflow(text)

        pnl_lines = cls._clean_lines(pnl)
        balance_lines = cls._clean_lines(balance)
        cashflow_lines = cls._clean_lines(cashflow)
        all_lines = cls._clean_lines(text)

        # -----------------------------------------------------
        # 2. REVENUE (TURNOVER FIRST — MOST RELIABLE)
        # -----------------------------------------------------

        revenue_raw = (
            cls._extract_table_value(pnl_lines, "turnover")
            or cls._extract_table_value(pnl_lines, "revenue")
        )

        if not revenue_raw:
            revenue_raw = cls._find_first([
                r"revenue[^0-9]*?(\d[\d,]*\.?\d*\s*[kKmMbB]?)",
            ], pnl)

        # -----------------------------------------------------
        # 3. CASH (BALANCE SHEET ONLY)
        # -----------------------------------------------------

        cash_raw = cls._extract_table_value(
            balance_lines,
            "cash and cash equivalents"
        )

        if not cash_raw:
            cash_raw = cls._find_first([
                r"cash\s+and\s+cash\s+equivalents[^0-9]*?(\d[\d,]*)",
            ], balance)

        # -----------------------------------------------------
        # 4. EBITDA (STRICT RULE: ONLY P&L ROW)
        # -----------------------------------------------------
        #
        # IMPORTANT:
        # We intentionally do NOT search narrative text anymore.
        # If EBITDA is not in the P&L table, we return 0.
        #
        # This fixes the "FY2028 EBITDA" bug permanently.
        # -----------------------------------------------------

        ebitda_raw = cls._extract_table_value(pnl_lines, "ebitda")

        # -----------------------------------------------------
        # 5. CUSTOMERS (NARRATIVE + TABLE SAFE)
        # -----------------------------------------------------

        customers_raw = cls._find_first([
            r"serving\s+(\d[\d,]*)\s+customer",
            r"(\d[\d,]*)\s+customers?",
        ], text)

        # -----------------------------------------------------
        # 6. MARGINS (USUALLY NOT IN TABLES)
        # -----------------------------------------------------

        gross_margin_raw = cls._find_first([
            r"gross\s+margin[^0-9]*?(\d[\d.]*)\s*%",
        ], text)

        operating_margin_raw = cls._find_first([
            r"operating\s+margin[^0-9]*?(\d[\d.]*)\s*%",
        ], text)

        # -----------------------------------------------------
        # 7. FINAL NORMALISATION
        # -----------------------------------------------------

        # `None` here means "not found in the document" -- distinct from a
        # legitimately-zero value (e.g. a pre-revenue or break-even
        # company), which callers need to be able to tell apart.
        revenue = cls._to_number(revenue_raw) if revenue_raw is not None else None
        cash = cls._to_number(cash_raw) if cash_raw is not None else None
        ebitda = cls._to_number(ebitda_raw) if ebitda_raw is not None else None

        customers = int(customers_raw.replace(",", "")) if customers_raw else None
        gross_margin = float(gross_margin_raw) if gross_margin_raw else None
        operating_margin = float(operating_margin_raw) if operating_margin_raw else None

        # -----------------------------------------------------
        # 8. RETURN STRUCTURE (UNCHANGED API)
        # -----------------------------------------------------

        return {
            "revenue": revenue,
            "cash": cash,
            "ebitda": ebitda,
            "customers": customers,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
        }