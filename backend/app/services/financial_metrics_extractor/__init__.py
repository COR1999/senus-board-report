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

Module layout
-------------

This was previously one ~1100-line file; split by concern (each grouping
already existed as a labeled section in the original file, just promoted
to real module boundaries):

- `_text_parsing.py` (`TextParsingMixin`) -- domain-agnostic section/line/
  number/table-lookup primitives.
- `_period_detection.py` (`PeriodDetectionMixin`) -- reporting-period/
  cadence detection and document-format recognition.
- `_field_extraction.py` (`FieldExtractionMixin`) -- the two field-
  extraction paths (half-year three-statement layout, Information
  Document single-summary-table layout).

`FinancialMetricsExtractor` below combines all three via plain multiple
inheritance -- every method across all three mixins is a classmethod or
staticmethod with no instance state, so `cls._helper(...)` calls resolve
across mixin boundaries via MRO exactly as if this were still one file.
Nothing outside this package needs to change: `from
app.services.financial_metrics_extractor import FinancialMetricsExtractor`
still works unchanged, since Python resolves that import from this
`__init__.py` whether the module is a single file or a package.
"""

from typing import Any, Dict, Optional

from ._field_extraction import FieldExtractionMixin
from ._period_detection import PeriodDetectionMixin
from ._text_parsing import TextParsingMixin


class FinancialMetricsExtractor(FieldExtractionMixin, PeriodDetectionMixin, TextParsingMixin):
    """
    Deterministic financial statement parser.
    No AI usage. Fully rule-based and structure-aware.
    """

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
        if (
            operating_cf is not None
            and investing_cf is not None
            and financing_cf is not None
            and opening_cash is not None
            and closing_cash is not None
        ):
            net_change = closing_cash - opening_cash
            cashflow_reconciles = (
                abs((operating_cf + investing_cf + financing_cf) - net_change)
                <= cls._RECONCILIATION_TOLERANCE
            )

        return {"pnl_reconciles": pnl_reconciles, "cashflow_reconciles": cashflow_reconciles}
