"""Deterministic valuation tools exposed to analysis agents."""

from __future__ import annotations

from financial_tool_utils import safe_float


def calculate_ddm(
    dividend_per_share_twd: float,
    cost_of_equity_pct: float,
    dividend_growth_pct: float = 2.0,
) -> dict:
    """Calculate Gordon-growth dividend discount model value per share."""
    if dividend_per_share_twd <= 0:
        return {"error": "dividend_per_share_twd must be positive"}
    cost_of_equity = cost_of_equity_pct / 100
    growth = dividend_growth_pct / 100
    if cost_of_equity <= growth:
        return {"error": "cost_of_equity_pct must exceed dividend_growth_pct"}
    next_dividend = dividend_per_share_twd * (1 + growth)
    value = next_dividend / (cost_of_equity - growth)
    return {
        "dividend_per_share_twd": round(dividend_per_share_twd, 4),
        "next_dividend_twd": round(next_dividend, 4),
        "cost_of_equity_pct": round(cost_of_equity_pct, 4),
        "dividend_growth_pct": round(dividend_growth_pct, 4),
        "value_per_share_twd": round(value, 4),
    }


def calculate_implied_revenue_growth(
    target_eps_twd: float,
    current_net_margin_pct: float,
    shares_outstanding: float,
    current_revenue_billion_twd: float,
    forecast_years: int = 1,
) -> dict:
    """Reverse-engineer the revenue CAGR required to support a target EPS."""
    inputs = {
        "target_eps_twd": safe_float(target_eps_twd),
        "current_net_margin_pct": safe_float(current_net_margin_pct),
        "shares_outstanding": safe_float(shares_outstanding),
        "current_revenue_billion_twd": safe_float(current_revenue_billion_twd),
        "forecast_years": safe_float(forecast_years),
    }
    for field, value in inputs.items():
        if value is None or value <= 0:
            return {"error": f"{field} must be positive"}
    if not inputs["forecast_years"].is_integer():
        return {"error": "forecast_years must be a positive integer"}

    target_eps = inputs["target_eps_twd"]
    net_margin_pct = inputs["current_net_margin_pct"]
    shares = inputs["shares_outstanding"]
    current_revenue = inputs["current_revenue_billion_twd"]
    years = inputs["forecast_years"]

    required_net_income_billion_twd = target_eps * shares / 1e9
    required_revenue_billion_twd = required_net_income_billion_twd / (net_margin_pct / 100)
    implied_cagr_pct = ((required_revenue_billion_twd / current_revenue) ** (1 / years) - 1) * 100
    return {
        "target_eps_twd": round(target_eps, 4),
        "current_net_margin_pct": round(net_margin_pct, 4),
        "shares_outstanding": round(shares, 4),
        "current_revenue_billion_twd": round(current_revenue, 4),
        "forecast_years": int(years),
        "required_net_income_billion_twd": round(required_net_income_billion_twd, 4),
        "required_revenue_billion_twd": round(required_revenue_billion_twd, 4),
        "implied_revenue_cagr_pct": round(implied_cagr_pct, 4),
    }
