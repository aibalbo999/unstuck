"""Deterministic enforcement of the short-term role's negative-FCF risk policy."""

from __future__ import annotations

import math


NEGATIVE_FCF_WARNING = "注意：自由現金流為負，短線財務壓力升高"
FINANCIAL_RISK_POLICY_VERSION = "negative-fcf:v2"


def negative_fcf_value(data):
    """Canonical finite raw fact; booleans and rounded presentation are not facts."""
    raw = data.get("free_cash_flow_raw") if isinstance(data, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        value = float(raw)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) and value < 0 else None


def enforce_trade_financial_risk(structured: dict, data: dict) -> dict:
    """Raise risk on the canonical raw TWD fact, without inventing its period.

    The prompt exposes this value as cash_flow.free_cash_flow_billion_twd.
    Inspect the unrounded raw fact so small negative values cannot round to zero.
    This policy never changes direction, prices, or source/completion validation.
    """
    value = negative_fcf_value(data)
    if value is None:
        return structured
    from trade_catalyst_claims import split_exact_policy_suffix
    catalyst, _ = split_exact_policy_suffix(structured.get("core_catalyst"))
    flags = structured.get("financial_risk_flags")
    flags = [flag for flag in flags if isinstance(flag, str)] if isinstance(flags, list) else []
    flags = list(dict.fromkeys([*flags, NEGATIVE_FCF_WARNING]))
    return {**structured, "risk_level": "High", "core_catalyst": catalyst,
            "financial_risk_flags": flags,
            "financial_risk_assessment": {
                "policy_version": FINANCIAL_RISK_POLICY_VERSION,
                "reason": "negative_free_cash_flow",
                "input_path": "data.free_cash_flow_raw", "value": value,
                "unit": "twd", "period": "not_verified",
            }}
