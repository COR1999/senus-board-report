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
    # SHARED EXTRACTION CORE
    # =========================================================

    @classmethod
    def _extract_all(cls, text: str) -> Dict[str, Any]:
        """
        Parses every field `extract()` and `extract_balance_sheet()` need,
        once, so both public methods can pull their own subset of keys
        without re-running section isolation/table parsing twice.
        """
        if not text:
            text = ""

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
