"""
The two field-extraction paths this extractor supports: the half-year
filing's three-statement layout (`_extract_all`), and the Information
Document's single summary-table layout (`_extract_all_information_document`).
This is the domain-specific layer -- it knows what "revenue"/"EBITDA"/
"cost of sales" mean and where to look for them; `_text_parsing.py` and
`_period_detection.py` only provide the generic primitives it's built on.
"""

import re
from typing import TYPE_CHECKING, Any, Dict

# Pylance/Pyright analyzes this mixin in isolation and can't see that
# __init__.py's FinancialMetricsExtractor combines it with
# TextParsingMixin/PeriodDetectionMixin via multiple inheritance -- every
# cls._helper(...) call below that's actually defined on one of those two
# sibling mixins otherwise reads as an unknown attribute. Erased at
# runtime (the `else` branch is what actually runs); exists purely so the
# type checker resolves these calls correctly, per Pyright's own
# documented pattern for this exact mixin scenario:
# https://microsoft.github.io/pyright/#/mixins
if TYPE_CHECKING:
    from ._period_detection import PeriodDetectionMixin

    # PeriodDetectionMixin (not TextParsingMixin) is the base here,
    # deliberately matching __init__.py's real base order
    # (FieldExtractionMixin, PeriodDetectionMixin, TextParsingMixin) --
    # PeriodDetectionMixin already type-inherits TextParsingMixin itself
    # (see _period_detection.py), so basing this on TextParsingMixin
    # directly instead would contradict that ordering and make C3
    # linearization impossible ("Cannot create consistent method
    # ordering"), confirmed directly via pyright.
    _FieldExtractionBase = PeriodDetectionMixin
else:
    _FieldExtractionBase = object


class FieldExtractionMixin(_FieldExtractionBase):
    """Requires `TextParsingMixin` and `PeriodDetectionMixin` to also be mixed in."""

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
