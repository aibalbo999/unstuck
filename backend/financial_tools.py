"""Deterministic financial calculation tools for agent prompts and Gemini tools."""

from __future__ import annotations

from typing import Any

from config import WACC_COST_OF_DEBT_DEFAULT_PCT, WACC_COST_OF_EQUITY_DEFAULT_PCT, WACC_TAX_RATE_DEFAULT_PCT
from financial_dcf_scenarios import build_dcf_scenarios
from financial_tool_utils import latest_numeric, pct_from_ratio, raw_twd_to_billion_twd, safe_float, safe_sequence
from financial_valuation_tools import calculate_ddm, calculate_implied_revenue_growth
from quant_metric_contract import calculate_quant_contract
from quant_input_contract import finite_number


def calculate_cagr(start_value: float, end_value: float, periods: int) -> dict:
    """Calculate CAGR as percentage points from positive start/end values."""
    if start_value <= 0 or end_value <= 0 or periods <= 0:
        return {"error": "start_value, end_value, and periods must be positive"}
    cagr_pct = ((end_value / start_value) ** (1 / periods) - 1) * 100
    if finite_number(cagr_pct) is None:
        return {"error": "CAGR calculation is non-finite"}
    return {
        "start_value": round(start_value, 4),
        "end_value": round(end_value, 4),
        "periods": periods,
        "cagr_pct": round(cagr_pct, 4),
    }


def calculate_dupont(net_margin_pct: float, asset_turnover: float, equity_multiplier: float) -> dict:
    """Decompose ROE into net margin, asset turnover, and equity multiplier."""
    if asset_turnover < 0 or equity_multiplier <= 0:
        return {"error": "asset_turnover must be non-negative and equity_multiplier must be positive"}
    roe_pct = float(net_margin_pct) * float(asset_turnover) * float(equity_multiplier)
    return {
        "net_margin_pct": round(float(net_margin_pct), 4),
        "asset_turnover": round(float(asset_turnover), 4),
        "equity_multiplier": round(float(equity_multiplier), 4),
        "roe_pct": round(roe_pct, 4),
        "formula": "ROE = net margin x asset turnover x equity multiplier",
    }


def calculate_wacc(
    market_cap_twd: float,
    total_debt_twd: float,
    cost_of_equity_pct: float = WACC_COST_OF_EQUITY_DEFAULT_PCT,
    cost_of_debt_pct: float = WACC_COST_OF_DEBT_DEFAULT_PCT,
    tax_rate_pct: float = WACC_TAX_RATE_DEFAULT_PCT,
) -> dict:
    """Calculate market-value WACC weights and WACC percentage."""
    market_cap_twd = max(float(market_cap_twd or 0), 0)
    total_debt_twd = max(float(total_debt_twd or 0), 0)
    invested_capital = market_cap_twd + total_debt_twd
    if invested_capital <= 0:
        return {"error": "market_cap_twd + total_debt_twd must be positive"}

    equity_weight = market_cap_twd / invested_capital
    debt_weight = total_debt_twd / invested_capital
    after_tax_debt_cost = cost_of_debt_pct * (1 - tax_rate_pct / 100)
    wacc_pct = equity_weight * cost_of_equity_pct + debt_weight * after_tax_debt_cost
    return {
        "market_cap_billion_twd": round(market_cap_twd / 1e9, 4),
        "total_debt_billion_twd": round(total_debt_twd / 1e9, 4),
        "equity_weight_pct": round(equity_weight * 100, 4),
        "debt_weight_pct": round(debt_weight * 100, 4),
        "cost_of_equity_pct": round(cost_of_equity_pct, 4),
        "after_tax_cost_of_debt_pct": round(after_tax_debt_cost, 4),
        "wacc_pct": round(wacc_pct, 4),
    }


def calculate_dcf(
    base_fcf_billion_twd: float,
    growth_rate_pct: float,
    wacc_pct: float,
    terminal_growth_pct: float,
    shares_outstanding: float,
    forecast_years: int = 5,
    net_debt_billion_twd: float = 0.0,
) -> dict:
    """Calculate a simple FCF DCF and return per-share value in TWD."""
    if base_fcf_billion_twd <= 0:
        return {"error": "base_fcf_billion_twd must be positive"}
    if shares_outstanding <= 0:
        return {"error": "shares_outstanding must be positive"}
    if forecast_years <= 0:
        return {"error": "forecast_years must be positive"}

    growth = growth_rate_pct / 100
    wacc = wacc_pct / 100
    terminal_growth = terminal_growth_pct / 100
    if wacc <= terminal_growth:
        return {"error": "wacc_pct must exceed terminal_growth_pct"}

    projected_fcf = []
    present_value_fcf = []
    for year in range(1, forecast_years + 1):
        fcf = base_fcf_billion_twd * ((1 + growth) ** year)
        pv = fcf / ((1 + wacc) ** year)
        projected_fcf.append(round(fcf, 4))
        present_value_fcf.append(round(pv, 4))

    terminal_fcf = projected_fcf[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    present_value_terminal = terminal_value / ((1 + wacc) ** forecast_years)
    enterprise_value = sum(present_value_fcf) + present_value_terminal
    equity_value = enterprise_value - net_debt_billion_twd
    price_per_share_twd = equity_value * 1e9 / shares_outstanding

    return {
        "base_fcf_billion_twd": round(base_fcf_billion_twd, 4),
        "growth_rate_pct": round(growth_rate_pct, 4),
        "wacc_pct": round(wacc_pct, 4),
        "terminal_growth_pct": round(terminal_growth_pct, 4),
        "forecast_years": forecast_years,
        "projected_fcf_billion_twd": projected_fcf,
        "present_value_fcf_billion_twd": present_value_fcf,
        "terminal_value_billion_twd": round(terminal_value, 4),
        "present_value_terminal_billion_twd": round(present_value_terminal, 4),
        "enterprise_value_billion_twd": round(enterprise_value, 4),
        "net_debt_billion_twd": round(net_debt_billion_twd, 4),
        "equity_value_billion_twd": round(equity_value, 4),
        "price_per_share_twd": round(price_per_share_twd, 4),
    }


def build_financial_tool_context(data: dict) -> dict:
    """Precompute deterministic tool outputs that agents can cite directly."""
    revenue_history = safe_sequence(dict.get(data, "revenue_history", []))
    net_income_history = safe_sequence(dict.get(data, "net_income_history", []))
    fcf_history = safe_sequence(dict.get(data, "fcf_history", []))
    sector = str(dict.get(data, "sector", "") or "")
    industry = str(dict.get(data, "industry", "") or "")

    tool_context: dict[str, Any] = calculate_quant_contract(
        data, wacc_calculator=calculate_wacc, scenario_builder=build_dcf_scenarios,
        dcf_calculator=calculate_dcf,
    )

    valid_revenue = [safe_float(v) for v in revenue_history if safe_float(v) is not None and safe_float(v) > 0]
    if len(valid_revenue) >= 2:
        tool_context["calculations"]["revenue_cagr"] = calculate_cagr(
            valid_revenue[0],
            valid_revenue[-1],
            len(valid_revenue) - 1,
        )

    latest_revenue_growth_pct = None
    if len(revenue_history) >= 2:
        prev_revenue = safe_float(revenue_history[-2])
        latest_revenue = safe_float(revenue_history[-1])
        if prev_revenue and latest_revenue:
            latest_revenue_growth_pct = finite_number((latest_revenue / prev_revenue - 1) * 100)
            tool_context["calculations"]["latest_annual_revenue_growth"] = {
                "growth_pct": round(latest_revenue_growth_pct, 4) if latest_revenue_growth_pct is not None else None,
                "formula": "latest annual revenue / prior annual revenue - 1",
            }

    latest_net_income = latest_numeric(net_income_history)
    latest_fcf = latest_numeric(fcf_history)
    if latest_net_income and latest_fcf is not None:
        fcf_conversion_pct = latest_fcf / latest_net_income * 100
        tool_context["calculations"]["latest_fcf_conversion"] = {
            "fcf_conversion_pct": round(fcf_conversion_pct, 4),
            "formula": "latest annual FCF / latest annual net income",
        }

    dividend_rate = safe_float(dict.get(data, "dividend_rate_raw"))
    dividend_yield = safe_float(dict.get(data, "dividend_yield_raw"))
    is_financial = any(keyword in f"{sector} {industry}" for keyword in ["Financial", "銀行", "金融", "保險", "金控"])
    if dividend_rate and (is_financial or (dividend_yield is not None and dividend_yield >= 0.05)):
        ddm_scenarios = {
            "conservative": calculate_ddm(dividend_rate, cost_of_equity_pct=9.0, dividend_growth_pct=0.5),
            "base": calculate_ddm(dividend_rate, cost_of_equity_pct=8.0, dividend_growth_pct=1.5),
            "optimistic": calculate_ddm(dividend_rate, cost_of_equity_pct=7.0, dividend_growth_pct=2.0),
        }
        tool_context["calculations"]["ddm_scenarios_default"] = {
            "reason": "financial sector or dividend yield above 5%; use DDM/PB as primary valuation cross-check",
            "dividend_yield_pct": round(dividend_yield * 100, 4) if dividend_yield is not None else None,
            "scenarios": ddm_scenarios,
        }

    return tool_context
