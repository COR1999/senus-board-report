"""
Tests for FinancialMetricsExtractor, particularly the new prior-period
comparative extraction and computed EBITDA/margins added for
backend/docs/metrics-expansion-plan.md.
"""
from pathlib import Path

import pytest

from app.services.financial_metrics_extractor import FinancialMetricsExtractor as FME
from app.services.pdf_service import PDFExtractionService

# Synthetic text mirroring the real filing's exact section layout (label,
# then current value, then prior value, each on its own line -- this is
# how this project's PDF extraction actually lays tables out, not
# space-separated on one line).
SYNTHETIC_FILING = """
Some cover page narrative mentioning EBITDA positive by FY2028, ignore this.

Consolidated Profit and Loss Account
for the six months ended 31 December 2025
Turnover
354,813
340,931
Cost of sales
64,861
69,600
Gross Profit
289,952
272,331
Administrative expenses
781,975
677,908
Group operating loss
483,753
405,577
Interest payable and similar expenses
1,391
1,036
Loss before taxation
485,144
406,613

Consolidated Balance Sheet
for the six months ended 31 December 2025
Cash and cash equivalents
735,189
72,382
Total Assets Less Current Liabilities
637,554
258,784
Creditors: amounts falling due after more than one
year
-76,474
-85,468

Consolidated cash flow statement
for the six months ended 31 December 2025
Depreciation
10,014
10,016
Movements in working capital
64,839
-53,584
Net Cash used in operating activities
-410,291
-450,181

Senus recorded revenue of €836,991, serving 138 customer accounts.

Continued momentum with agri corporates and financial institutions with pipeline deals of
approx. €700k across 21 enterprise customers closed in the period (further approx. €500k
of open pipeline).

Half Year Results for the 6 months ended 31 December 2025 (HY2026).
Group Revenue up 4.1% to €354.8k (HY25: €340.9k).
"""


class TestExtractComputesEbitdaFromStructuredLines:
    """
    There is no literal "EBITDA" line in this filing (a common situation
    for real filings) -- EBITDA must be derived from operating result +
    depreciation add-back, not searched for as a keyword.
    """

    def test_ebitda_is_operating_result_plus_depreciation(self):
        result = FME.extract(SYNTHETIC_FILING)
        # -483,753 (loss) + 10,014 (depreciation add-back) = -473,739
        assert result["ebitda"] == -473_739.0
        assert result["ebitda_prior"] == -395_561.0

    def test_reporting_period_end_is_extracted_from_ended_date(self):
        # "for the six months ended 31 December 2025" appears (identically)
        # above each of the P&L/Balance Sheet/cash flow sections in
        # SYNTHETIC_FILING -- the first match is enough since they always
        # agree. Prior-period end is derived as the same month one year
        # earlier (half-year filings always compare like-for-like halves).
        result = FME.extract(SYNTHETIC_FILING)
        assert result["reporting_period_end"] == "Dec 2025"
        assert result["reporting_period_end_prior"] == "Dec 2024"

    def test_reporting_period_start_is_five_months_before_end(self):
        # Jul 2025 - Dec 2025 is a 6-month range inclusive of both ends.
        result = FME.extract(SYNTHETIC_FILING)
        assert result["reporting_period_start"] == "Jul 2025"
        assert result["reporting_period_start_prior"] == "Jul 2024"

    def test_missing_ended_date_leaves_period_start_none(self):
        result = FME.extract("No 'ended DD Month YYYY' text in this document at all.")
        assert result["reporting_period_end"] is None
        assert result["reporting_period_end_prior"] is None
        assert result["reporting_period_start"] is None
        assert result["reporting_period_start_prior"] is None

    def test_full_year_filing_uses_eleven_month_offset_not_five(self):
        # Regression guard: the "ended DD Month YYYY" regex matches "twelve
        # months ended" just as readily as "six months ended" -- without
        # cadence detection this would wrongly compute a 6-month-back start
        # ("Jan 2026") instead of the true 12-month-back start ("Jul 2025").
        full_year_filing = """
        Annual Report for the twelve months ended 30 June 2026.
        Group Revenue up 4.1% to €700.0k (FY25: €672.0k).
        """
        result = FME.extract(full_year_filing)
        assert result["reporting_period_end"] == "Jun 2026"
        assert result["reporting_period_end_prior"] == "Jun 2025"
        assert result["reporting_period_start"] == "Jul 2025"
        assert result["reporting_period_start_prior"] == "Jul 2024"

    def test_ambiguous_cadence_leaves_period_start_none_not_guessed(self):
        # An "ended DD Month YYYY" match with no "six"/"twelve"/"half"/"full"
        # cadence cue anywhere -- cadence can't be determined, so the start
        # fields must stay None rather than defaulting to a half-year guess
        # that might be wrong. The end date itself is still extracted since
        # it doesn't depend on cadence.
        ambiguous_filing = "Results for the period ended 31 December 2025."
        result = FME.extract(ambiguous_filing)
        assert result["reporting_period_end"] == "Dec 2025"
        assert result["reporting_period_end_prior"] == "Dec 2024"
        assert result["reporting_period_start"] is None
        assert result["reporting_period_start_prior"] is None

    def test_narrative_ebitda_fy2028_mention_is_not_picked_up(self):
        result = FME.extract(SYNTHETIC_FILING)
        # Regression guard for the exact bug class this extractor was
        # rewritten to fix -- "EBITDA positive during FY2028" must never
        # produce ebitda=2028 or similar narrative leakage.
        assert result["ebitda"] != 2028


class TestExtractBookings:
    r"""
    Narrative-only, same reliability class as `customers` (not a
    structured table value) -- e.g. "pipeline deals of approx. €700k
    across 21 enterprise customers closed in the period (further approx.
    €500k of open pipeline)". The real filing wraps this sentence across
    multiple OCR'd lines, so SYNTHETIC_FILING mirrors that exact wrapping
    to make sure `\s+` (not literal spaces) correctly bridges the linebreaks.
    """

    def test_extracts_closed_value_and_customer_count(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert result["bookings_value"] == 700_000.0
        assert result["bookings_customers"] == 21

    def test_extracts_open_pipeline(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert result["bookings_pipeline"] == 500_000.0

    def test_missing_bookings_sentence_is_none_not_zero(self):
        result = FME.extract("No bookings narrative in this document at all.")
        assert result["bookings_value"] is None
        assert result["bookings_customers"] is None
        assert result["bookings_pipeline"] is None


class TestExtractReportingPeriod:
    """
    Narrative-only, extracted directly from the filing's own labels (e.g.
    "(HY2026)" for the current period, the recurring "(HY25:" for the prior
    comparative), NOT derived from `extracted_at` (upload/processing time,
    not the period covered) and NOT dependent on the AI/Gemini path. The
    2-digit prior year is normalized to 4 digits ("HY25" -> "HY2025") so the
    UI doesn't show "HY25 vs HY2026" side by side -- confirmed inconsistent-
    looking by the user testing the live dashboard.
    """

    def test_extracts_current_and_prior_period_labels(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert result["reporting_period"] == "HY2026"
        assert result["reporting_period_prior"] == "HY2025"

    def test_missing_period_labels_are_none_not_guessed(self):
        result = FME.extract("No period labels in this document at all.")
        assert result["reporting_period"] is None
        assert result["reporting_period_prior"] is None


class TestExtractPriorPeriodComparative:
    def test_revenue_current_and_prior(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert result["revenue"] == 354_813.0
        assert result["revenue_prior"] == 340_931.0

    def test_cash_current_and_prior(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert result["cash"] == 735_189.0
        assert result["cash_prior"] == 72_382.0

    def test_gross_margin_computed_from_gross_profit_over_revenue(self):
        result = FME.extract(SYNTHETIC_FILING)
        # 289,952 / 354,813 * 100
        assert round(result["gross_margin"], 1) == 81.7
        assert round(result["gross_margin_prior"], 1) == 79.9

    def test_operating_margin_computed_from_operating_result_over_revenue(self):
        result = FME.extract(SYNTHETIC_FILING)
        assert round(result["operating_margin"], 1) == -136.3

    def test_customers_has_no_prior_key_value(self):
        # No structured comparative source exists for customers -- the one
        # narrative figure is a fixed FY reference, not a period pair.
        result = FME.extract(SYNTHETIC_FILING)
        assert result["customers"] == 138
        assert "customers_prior" not in result

    def test_missing_field_is_none_not_zero(self):
        result = FME.extract("No financial statements here at all.")
        assert result["revenue"] is None
        assert result["ebitda"] is None
        assert result["customers"] is None


class TestExtractBalanceSheet:
    def test_total_debt_extracted_from_wrapped_label_and_made_positive(self):
        """
        The real label ("Creditors: amounts falling due after more than
        one year") wraps across two OCR'd lines -- this is a regression
        test for that exact parsing gap, and for the sign flip (the
        filing prints debt as a negative liability figure; total_debt
        should be stored as a positive magnitude).
        """
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["total_debt"] == 76_474.0
        assert result["total_debt_prior"] == 85_468.0

    def test_net_cash_used_operating_made_positive(self):
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["net_cash_used_operating"] == 410_291.0
        assert result["net_cash_used_operating_prior"] == 450_181.0

    def test_working_capital_change_stays_signed(self):
        # Unlike debt/burn, this is legitimately positive or negative --
        # must NOT be forced to a magnitude.
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["working_capital_change"] == 64_839.0
        assert result["working_capital_change_prior"] == -53_584.0

    def test_capital_employed(self):
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["capital_employed"] == 637_554.0
        assert result["capital_employed_prior"] == 258_784.0

    def test_cost_of_sales_and_administrative_expenses(self):
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["cost_of_sales"] == 64_861.0
        assert result["cost_of_sales_prior"] == 69_600.0
        assert result["administrative_expenses"] == 781_975.0
        assert result["administrative_expenses_prior"] == 677_908.0

    def test_operating_result_is_negative_for_a_loss(self):
        result = FME.extract_balance_sheet(SYNTHETIC_FILING)
        assert result["operating_result"] == -483_753.0
        assert result["operating_result_prior"] == -405_577.0

    def test_missing_balance_sheet_fields_are_none(self):
        result = FME.extract_balance_sheet("No financial statements here at all.")
        assert result["total_debt"] is None
        assert result["capital_employed"] is None


class TestExtractAgainstRealFiling:
    """
    Locks in the real numbers from the actual uploaded filing as a
    regression fixture -- if OCR/section-isolation logic ever changes,
    this catches a real-world regression that synthetic text might miss.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def real_text(cls):
        pdf_path = (
            Path(__file__).resolve().parent.parent
            / "uploads"
            / "Senus_HalfYearResultsDec2025_PR_V19032026 FINAL clean.pdf"
        )
        content = pdf_path.read_bytes()
        _, text = PDFExtractionService.extract_text_from_upload(content, "test.pdf")
        return text

    def test_extract_matches_known_real_values(self, real_text):
        result = FME.extract(real_text)
        assert result["revenue"] == 354_813.0
        assert result["revenue_prior"] == 340_931.0
        assert result["cash"] == 735_189.0
        assert result["ebitda"] == -473_739.0
        assert result["customers"] == 138
        assert result["bookings_value"] == 700_000.0
        assert result["bookings_customers"] == 21
        assert result["bookings_pipeline"] == 500_000.0
        assert result["reporting_period"] == "HY2026"
        assert result["reporting_period_prior"] == "HY2025"
        assert result["reporting_period_end"] == "Dec 2025"
        assert result["reporting_period_end_prior"] == "Dec 2024"
        assert result["reporting_period_start"] == "Jul 2025"
        assert result["reporting_period_start_prior"] == "Jul 2024"

    def test_extract_balance_sheet_matches_known_real_values(self, real_text):
        result = FME.extract_balance_sheet(real_text)
        assert result["total_debt"] == 76_474.0
        assert result["interest_expense"] == 1_391.0
        assert result["capital_employed"] == 637_554.0
        assert result["net_cash_used_operating"] == 410_291.0
