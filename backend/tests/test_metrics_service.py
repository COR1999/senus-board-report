"""Unit tests for MetricsService's calculation formulas."""
from app.services.metrics_service import MetricsService


class TestFormatCurrency:
    def test_positive_magnitudes(self):
        assert MetricsService.format_currency(500) == "€500"
        assert MetricsService.format_currency(1_500) == "€2K"
        assert MetricsService.format_currency(1_500_000) == "€1.5M"
        assert MetricsService.format_currency(2_000_000_000) == "€2.0B"

    def test_negative_amount_formats_sign_before_symbol(self):
        # Not "€-474000" -- the sign belongs before the currency symbol.
        assert MetricsService.format_currency(-473_739) == "-€474K"
        assert MetricsService.format_currency(-500) == "-€500"

    def test_none_defaults_to_zero(self):
        assert MetricsService.format_currency(None) == "€0"


class TestCalculateChange:
    def test_positive_to_positive(self):
        assert MetricsService.calculate_change(110, 100) == 10

    def test_previous_zero_returns_zero(self):
        assert MetricsService.calculate_change(100, 0) == 0.0

    def test_negative_base_direction_matches_raw_value_movement(self):
        """
        A loss narrowing from -156.7 to -75.9 is a real improvement (the
        raw value increased) -- dividing by plain `previous` would report
        this as a *decrease* since both operands are negative. Regression
        test for that exact bug, found while building the ROCE KPI.
        """
        change = MetricsService.calculate_change(-75.9, -156.7)
        assert change > 0  # raw value went up -> percent change must read positive

    def test_negative_base_worsening_loss_is_negative(self):
        # -473,739 is a *bigger* loss than -395,561 -- change must be negative.
        change = MetricsService.calculate_change(-473_739, -395_561)
        assert change < 0

    def test_positive_base_unaffected_by_abs_fix(self):
        # Sanity check: the abs(previous) fix must be a no-op whenever
        # previous was already positive (the common case for revenue/cash/etc).
        assert MetricsService.calculate_change(120, 100) == 20
        assert MetricsService.calculate_change(80, 100) == -20


class TestEbitdaMargin:
    def test_computes_percentage(self):
        assert round(MetricsService.ebitda_margin(100, 1000), 2) == 10.0

    def test_none_ebitda_returns_none(self):
        assert MetricsService.ebitda_margin(None, 1000) is None

    def test_zero_or_none_revenue_returns_none(self):
        assert MetricsService.ebitda_margin(100, 0) is None
        assert MetricsService.ebitda_margin(100, None) is None

    def test_negative_ebitda_allowed(self):
        assert MetricsService.ebitda_margin(-473_739, 354_813) < 0


class TestInterestCover:
    def test_computes_ratio(self):
        assert round(MetricsService.interest_cover(10_000, 1_000), 2) == 10.0

    def test_none_ebitda_returns_none(self):
        assert MetricsService.interest_cover(None, 1_000) is None

    def test_zero_or_none_interest_expense_returns_none(self):
        assert MetricsService.interest_cover(10_000, 0) is None
        assert MetricsService.interest_cover(10_000, None) is None


class TestRoce:
    def test_computes_percentage(self):
        assert round(MetricsService.roce(100_000, 500_000), 2) == 20.0

    def test_none_operating_result_returns_none(self):
        assert MetricsService.roce(None, 500_000) is None

    def test_zero_or_negative_capital_employed_returns_none(self):
        assert MetricsService.roce(100_000, 0) is None
        assert MetricsService.roce(100_000, -50_000) is None


class TestCashRunwayMonths:
    def test_computes_months_of_runway(self):
        # €735,189 cash, €410,291 used over 6 months -> ~68,382/month burn
        result = MetricsService.cash_runway_months(735_189, 410_291, period_months=6)
        assert result is not None
        assert 10 < result < 11

    def test_none_cash_returns_none(self):
        assert MetricsService.cash_runway_months(None, 410_291) is None

    def test_cash_flow_positive_returns_none_not_infinity(self):
        # net_cash_used_operating <= 0 means operations aren't burning cash --
        # "runway" isn't a meaningful concept, so this must be None, not a
        # divide-by-zero or a nonsensical negative "runway".
        assert MetricsService.cash_runway_months(735_189, 0) is None
        assert MetricsService.cash_runway_months(735_189, -50_000) is None
