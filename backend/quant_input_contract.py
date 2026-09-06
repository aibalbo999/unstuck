"""Finite raw financial facts and separately identified valuation policy."""

from __future__ import annotations

import math

from mapping_fields import safe_mapping_dict

from config import (
    WACC_COST_OF_DEBT_DEFAULT_PCT, WACC_COST_OF_EQUITY_DEFAULT_PCT,
    WACC_CREDIT_SPREAD_DEFAULT_PCT, WACC_EQUITY_RISK_PREMIUM_DEFAULT_PCT,
    WACC_TAX_RATE_DEFAULT_PCT,
)


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def read_quant_inputs(data):
    """Read only named raw fields; histories have the provider's billion-TWD contract."""
    data = safe_mapping_dict(data) or {}
    facts, provenance, invalid = {}, {}, {}
    units = {
        "shares_raw": "shares", "current_price": "twd_per_share",
        "market_cap_raw": "twd", "total_debt_raw": "twd",
        "total_cash_raw": "twd", "free_cash_flow_raw": "twd",
    }
    for field, unit in units.items():
        number = finite_number(data.get(field))
        facts[field] = number
        provenance[field] = {"path": f"data.{field}", "unit": unit, "value": number}
        if number is None:
            invalid[field] = f"{field}_missing_or_invalid"
        elif field in {"shares_raw", "current_price", "market_cap_raw"} and number <= 0:
            invalid[field] = f"{field}_non_positive"
        elif field in {"total_debt_raw", "total_cash_raw"} and number < 0:
            invalid[field] = f"{field}_negative"

    base_fcf = facts["free_cash_flow_raw"]
    facts["base_fcf_billion_twd"] = base_fcf / 1e9 if base_fcf is not None else None
    # A present invalid or negative raw fact never gets replaced by an older history.
    if data.get("free_cash_flow_raw") is None:
        history = data.get("fcf_history")
        if isinstance(history, (list, tuple)):
            for index in range(len(history) - 1, -1, -1):
                if history[index] is None:
                    continue
                base_fcf = finite_number(history[index])
                facts["base_fcf_billion_twd"] = base_fcf
                provenance["free_cash_flow_raw"] = {
                    "path": f"data.fcf_history[{index}]", "unit": "billion_twd", "value": base_fcf,
                }
                if base_fcf is not None:
                    invalid.pop("free_cash_flow_raw", None)
                break
    if facts["base_fcf_billion_twd"] is not None and facts["base_fcf_billion_twd"] <= 0:
        invalid["free_cash_flow_raw"] = "free_cash_flow_raw_non_positive"

    eps_field = "trailing_eps" if "trailing_eps" in data else "eps"
    facts["eps"] = finite_number(data.get(eps_field))
    provenance["eps"] = {"path": f"data.{eps_field}", "unit": "twd_per_share", "value": facts["eps"]}
    if facts["eps"] is None:
        invalid["eps"] = "eps_missing_or_invalid"
    elif facts["eps"] <= 0:
        invalid["eps"] = "eps_non_positive"
    requirements = {
        "wacc": ("market_cap_raw", "total_debt_raw"),
        "dcf": ("market_cap_raw", "total_debt_raw", "total_cash_raw", "shares_raw", "free_cash_flow_raw"),
        "implied_pe": ("current_price", "eps"),
    }
    reasons = {metric: [invalid[field] for field in fields if field in invalid]
               for metric, fields in requirements.items()}
    return facts, provenance, reasons


def wacc_policy(data):
    data = safe_mapping_dict(data) or {}
    macro = safe_mapping_dict(data.get("macro_indicators")) or {}
    indicators = safe_mapping_dict(macro.get("indicators")) or {}
    rate = safe_mapping_dict(indicators.get("us_10y_yield")) or {}
    risk_free = finite_number(rate.get("value"))
    tax = finite_number(data.get("tax_rate"))
    tax_pct = tax * 100 if tax is not None and 0 <= tax <= 1 else WACC_TAX_RATE_DEFAULT_PCT
    policy = {
        "tax_rate_pct": tax_pct, "tax_rate_source": "data.tax_rate" if tax is not None and 0 <= tax <= 1 else "configured_policy",
        "risk_free_rate_pct": risk_free, "risk_free_rate_source": "default",
        "cost_of_equity_pct": WACC_COST_OF_EQUITY_DEFAULT_PCT,
        "cost_of_debt_pct": WACC_COST_OF_DEBT_DEFAULT_PCT,
        "equity_beta": None, "equity_risk_premium_pct": None, "credit_spread_pct": None,
        "uses_market_rate": risk_free is not None, "kind": "assumption",
    }
    if risk_free is not None:
        beta = finite_number(data.get("beta", data.get("equity_beta")))
        beta = beta if beta is not None and beta > 0 else 1.0
        premium = finite_number(data.get("equity_risk_premium_pct", data.get("market_risk_premium_pct")))
        premium = premium if premium is not None else WACC_EQUITY_RISK_PREMIUM_DEFAULT_PCT
        spread = finite_number(data.get("credit_spread_pct"))
        spread = spread if spread is not None else WACC_CREDIT_SPREAD_DEFAULT_PCT
        debt_cost = finite_number(data.get("cost_of_debt_pct"))
        policy.update({
            "risk_free_rate_source": f"FRED:{rate.get('series_id') or 'DGS10'}",
            "cost_of_equity_pct": max(risk_free + beta * premium, risk_free),
            "cost_of_debt_pct": debt_cost if debt_cost is not None else max(risk_free + spread, 0),
            "equity_beta": beta, "equity_risk_premium_pct": premium, "credit_spread_pct": spread,
        })
    return policy
