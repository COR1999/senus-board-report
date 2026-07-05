from typing import Dict


class MetricsService:
    """Business logic helpers for financial metrics."""

    @staticmethod
    def format_currency(amount: float | None, currency: str = "EUR") -> str:
        """Format a numeric amount as a readable currency string."""
        if amount is None:
            amount = 0.0

        symbol = "€" if currency.upper() == "EUR" else "$"

        if amount >= 1_000_000_000:
            return f"{symbol}{amount / 1_000_000_000:.1f}B"

        if amount >= 1_000_000:
            return f"{symbol}{amount / 1_000_000:.1f}M"

        if amount >= 1_000:
            return f"{symbol}{amount / 1_000:.0f}K"

        return f"{symbol}{amount:.0f}"

    @staticmethod
    def calculate_change(current: float | None, previous: float | None) -> float:
        """Percentage change between two values."""
        current = current or 0
        previous = previous or 0

        if previous == 0:
            return 0.0

        return ((current - previous) / previous) * 100

    @staticmethod
    def get_trend(change: float) -> str:
        """Return trend direction."""
        if change > 0:
            return "up"
        if change < 0:
            return "down"
        return "neutral"

    @staticmethod
    def calculate_margins(
        revenue: float,
        gross_profit: float,
        operating_profit: float,
        net_income: float,
    ) -> Dict[str, float]:
        """Calculate profitability margins."""

        if revenue <= 0:
            return {
                "gross_margin": 0.0,
                "operating_margin": 0.0,
                "net_margin": 0.0,
            }

        return {
            "gross_margin": (gross_profit / revenue) * 100,
            "operating_margin": (operating_profit / revenue) * 100,
            "net_margin": (net_income / revenue) * 100,
        }

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

    @staticmethod
    def calculate_debt_ratios(
        debt: float,
        ebitda: float,
        cash: float,
        revenue: float | None = None,
    ) -> Dict[str, float]:
        """Calculate debt ratios."""

        return {
            "net_debt": debt - cash,
            "debt_to_ebitda": debt / ebitda if ebitda > 0 else 0.0,
            "debt_to_revenue": (
                debt / revenue
                if revenue and revenue > 0
                else 0.0
            ),
        }