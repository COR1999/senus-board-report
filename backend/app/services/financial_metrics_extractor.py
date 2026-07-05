import re
from typing import Dict, Any, List, Optional


class FinancialMetricsExtractor:
    """
    Deterministic extractor (NO AI).
    This is your source of truth layer.
    """

    @staticmethod
    def _to_number(value: Optional[str]) -> float:
        if not value:
            return 0

        value = value.lower().replace(",", "")
        multiplier = 1

        if "k" in value:
            multiplier = 1_000
        elif "m" in value:
            multiplier = 1_000_000
        elif "b" in value:
            multiplier = 1_000_000_000

        nums = re.findall(r"-?[\d.]+", value)
        return float(nums[0]) * multiplier if nums else 0

    @staticmethod
    def _find_first(patterns: List[str], text: str) -> Optional[str]:
        """Try each pattern in order, most specific first, return first hit."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @classmethod
    def extract(cls, text: str) -> Dict[str, Any]:

        if not text:
            text = ""

        # NOTE: every capture group below uses \d[\d,]* rather than
        # [\d,]+. The comma-inclusive class alone can match a bare
        # punctuation comma with zero digits (e.g. "solutions, \ncustomer"),
        # which then blows up downstream when int()/float() gets an
        # empty string after stripping commas. Requiring a leading \d
        # guarantees at least one real digit was captured.

        # --------------------------------------------------------
        # Revenue: handle "Revenue up 12% to €50.2m" BEFORE falling
        # back to a generic "revenue ... number" pattern, otherwise
        # the generic pattern grabs the percentage instead.
        # --------------------------------------------------------
        revenue_raw = cls._find_first([
            r"revenue[^%]*?(?:up|down|increased|decreased|grew)\s+[\d.]+%\s+to\s+[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
            r"(?:total|group|annual)\s+revenue[^0-9]*?[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
            r"revenue[^0-9]*?[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
        ], text)

        # --------------------------------------------------------
        # Cash
        # --------------------------------------------------------
        cash_raw = cls._find_first([
            r"cash\s+and\s+cash\s+equivalents[^0-9]*?[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
            r"cash\s+(?:balance|position)[^0-9]*?[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
            r"cash[^0-9]*?[€$]?(\d[\d,]*\.?\d*\s*[kmb]?)",
        ], text)

        # --------------------------------------------------------
        # EBITDA - allow leading minus for losses, skip past % changes
        # --------------------------------------------------------
        ebitda_raw = cls._find_first([
            r"ebitda[^%]*?(?:up|down|increased|decreased|grew)\s+[\d.]+%\s+to\s+[€$]?(-?\d[\d,]*\.?\d*\s*[kmb]?)",
            r"ebitda[^0-9\-]*?[€$]?(-?\d[\d,]*\.?\d*\s*[kmb]?)",
        ], text)

        # --------------------------------------------------------
        # Customers - try "N customers" (most common phrasing) before
        # falling back to "customers: N"
        # --------------------------------------------------------
        customers_raw = cls._find_first([
            r"(\d[\d,]*)\s+customers?",
            r"customers?[^0-9]*?(\d[\d,]*)",
        ], text)

        # --------------------------------------------------------
        # Margins
        # --------------------------------------------------------
        gross_margin_raw = cls._find_first([
            r"gross\s+margin[^0-9]*?(\d[\d.]*)\s*%",
            r"gross\s+margin[^0-9]*?(\d[\d.]*)",
        ], text)

        operating_margin_raw = cls._find_first([
            r"operating\s+margin[^0-9]*?(\d[\d.]*)\s*%",
            r"operating\s+margin[^0-9]*?(\d[\d.]*)",
        ], text)

        return {
            "revenue": cls._to_number(revenue_raw),
            "cash": cls._to_number(cash_raw),
            "ebitda": cls._to_number(ebitda_raw),
            "customers": int(customers_raw.replace(",", "")) if customers_raw else 0,
            "gross_margin": float(gross_margin_raw) if gross_margin_raw else 0,
            "operating_margin": float(operating_margin_raw) if operating_margin_raw else 0,
        }