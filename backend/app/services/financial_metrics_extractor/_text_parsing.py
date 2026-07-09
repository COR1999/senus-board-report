"""
Low-level, domain-agnostic text/table parsing primitives shared by every
extraction path in this package. Nothing here knows about "revenue" or
"EBITDA" specifically -- see `_field_extraction.py` for the field-level
logic that calls these.
"""

import re
from typing import List, Optional, Tuple


class TextParsingMixin:
    """Section isolation, number parsing, and label/table lookup helpers."""

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
