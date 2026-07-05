from typing import Dict


class MetricsService:
    """Utility helpers for common financial metric calculations."""

    @staticmethod
    def calculate_margins(revenue: float, operating_profit: float, net_income: float) -> Dict[str, float]:
        """Calculate profitability margins."""
        if revenue <= 0:
            return {
                "gross_margin": 0.0,
                "operating_margin": 0.0,
                "net_margin": 0.0,
            }

        return {
            "gross_margin": (revenue - operating_profit) / revenue * 100,
            "operating_margin": operating_profit / revenue * 100,
            "net_margin": net_income / revenue * 100,
        }

    @staticmethod
    def calculate_cagr(start_value: float, end_value: float, years: int) -> float:
        """Calculate Compound Annual Growth Rate."""
        if start_value <= 0 or years <= 0:
            return 0.0
        return ((end_value / start_value) ** (1 / years) - 1) * 100

    @staticmethod
    def calculate_cash_runway(monthly_burn_rate: float, cash_balance: float) -> float:
        """Calculate months of runway."""
        if monthly_burn_rate <= 0:
            return 0.0
        return cash_balance / monthly_burn_rate

    @staticmethod
    def calculate_debt_ratios(debt: float, ebitda: float, cash: float, revenue: float | None = None) -> Dict[str, float]:
        """Calculate debt service ratios."""
        debt_to_revenue = debt / revenue if revenue and revenue > 0 else 0.0
        return {
            "net_debt": debt - cash,
            "debt_to_ebitda": debt / ebitda if ebitda > 0 else 0.0,
            "debt_to_revenue": debt_to_revenue,
        }