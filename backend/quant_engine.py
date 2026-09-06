"""Quantitative metric entry point using the shared financial tool contract."""

from __future__ import annotations

from financial_tools import build_financial_tool_context, calculate_wacc


class QuantEngine:
    @staticmethod
    def calculate_wacc(equity, debt, cost_of_equity, cost_of_debt, tax_rate):
        """Compatibility facade: ratio inputs/output, tool uses percentage points."""
        result = calculate_wacc(equity, debt, cost_of_equity * 100, cost_of_debt * 100, tax_rate * 100)
        return round(result.get("wacc_pct", 0) / 100, 4)

    @staticmethod
    def calculate_dcf(free_cash_flows, wacc, terminal_growth_rate, shares_outstanding):
        """Legacy explicit projected-cash-flow helper, never a canonical metric source."""
        if not free_cash_flows or wacc <= terminal_growth_rate or shares_outstanding <= 0:
            return 0.0
        pv_fcf = sum(fcf / ((1 + wacc) ** i) for i, fcf in enumerate(free_cash_flows, 1))
        terminal_value = free_cash_flows[-1] * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)
        pv_tv = terminal_value / ((1 + wacc) ** len(free_cash_flows))
        return round((pv_fcf + pv_tv) / shares_outstanding, 2)

    @staticmethod
    def compute_all(data):
        """Prompt, task metrics, audit and report consume this same calculation result."""
        return build_financial_tool_context(data)
