class MetricsService:
    """Business logic helpers for financial metrics."""

    @staticmethod
    def format_currency(amount: float | None, currency: str = "EUR") -> str:
        """
        Format a numeric amount as a readable currency string. Handles
        negative values (e.g. a loss-making EBITDA) by formatting the
        magnitude and prefixing a sign, rather than embedding "-" between
        the currency symbol and digits (e.g. "-€474K", not "€-473739").
        """
        if amount is None:
            amount = 0.0

        symbol = "€" if currency.upper() == "EUR" else "$"
        sign = "-" if amount < 0 else ""
        magnitude = abs(amount)

        if magnitude >= 1_000_000_000:
            return f"{sign}{symbol}{magnitude / 1_000_000_000:.1f}B"

        if magnitude >= 1_000_000:
            return f"{sign}{symbol}{magnitude / 1_000_000:.1f}M"

        if magnitude >= 1_000:
            return f"{sign}{symbol}{magnitude / 1_000:.0f}K"

        return f"{sign}{symbol}{magnitude:.0f}"

    @staticmethod
    def calculate_change(current: float | None, previous: float | None) -> float:
        """
        Percentage change between two values. Divides by abs(previous), not
        previous -- the plain-`previous` formula flips sign in a way that
        contradicts the raw value's actual direction whenever `previous` is
        negative (e.g. a loss narrowing from -156.7 to -75.9 is a real
        improvement, but current/previous both negative makes the naive
        formula read as a *decrease*). abs(previous) matches the standard
        fix for this well-known "percentage change of a negative base"
        problem, and is a no-op whenever `previous` is already positive (the
        common case), so it changes nothing for existing all-positive metrics.
        """
        current = current or 0
        previous = previous or 0

        if previous == 0:
            return 0.0

        return ((current - previous) / abs(previous)) * 100

    @staticmethod
    def get_trend(change: float) -> str:
        """Return trend direction."""
        if change > 0:
            return "up"
        if change < 0:
            return "down"
        return "neutral"

    @staticmethod
    def ebitda_margin(ebitda: float | None, revenue: float | None) -> float | None:
        """EBITDA as a percentage of revenue. None if either input is missing or revenue <= 0."""
        if ebitda is None or not revenue or revenue <= 0:
            return None
        return (ebitda / revenue) * 100

    @staticmethod
    def interest_cover(ebitda: float | None, interest_expense: float | None) -> float | None:
        """
        EBITDA / interest expense -- a Debt Service Coverage Ratio proxy.
        Real DSCR also nets out principal repayments, which this filing
        (like most half-year filings) doesn't disclose separately -- see
        backend/docs/metrics-expansion-plan.md. None if either input is
        missing or interest_expense <= 0.
        """
        if ebitda is None or not interest_expense or interest_expense <= 0:
            return None
        return ebitda / interest_expense

    @staticmethod
    def roce(operating_result: float | None, capital_employed: float | None) -> float | None:
        """
        Return on Capital Employed: operating result (EBIT) / capital
        employed, as a percentage. Uses EBIT rather than EBITDA -- ROCE is
        conventionally a post-depreciation measure of how efficiently
        capital generates returns. None if either input is missing or
        capital_employed <= 0.
        """
        if operating_result is None or not capital_employed or capital_employed <= 0:
            return None
        return (operating_result / capital_employed) * 100

    @staticmethod
    def cash_runway_months(
        cash: float | None,
        net_cash_used_operating: float | None,
        period_months: float = 6,
    ) -> float | None:
        """
        Months of operating runway at the current cash-burn rate, derived
        from the cash flow statement's "Net cash used in operating
        activities" line over the filing period -- not period-over-period
        cash balance change, which would conflate financing activity (e.g.
        an equity raise) with actual operating burn. None if cash/burn data
        is missing, or operations are already cash-flow positive
        (net_cash_used_operating <= 0 -- "runway" isn't a meaningful concept
        when the company isn't burning cash).
        """
        if cash is None or not net_cash_used_operating or net_cash_used_operating <= 0:
            return None
        monthly_burn = net_cash_used_operating / period_months
        return MetricsService.calculate_cash_runway(monthly_burn, cash)

    @staticmethod
    def calculate_cagr(
        start_value: float,
        end_value: float,
        years: int,
    ) -> float:
        """Compound Annual Growth Rate."""

        if start_value <= 0 or years <= 0:
            return 0.0

        return ((end_value / start_value) ** (1 / years) - 1) * 100

    @staticmethod
    def calculate_cash_runway(
        monthly_burn_rate: float,
        cash_balance: float,
    ) -> float:
        """Calculate runway in months."""

        if monthly_burn_rate <= 0:
            return 0.0

        return cash_balance / monthly_burn_rate

