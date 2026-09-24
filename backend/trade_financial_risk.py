"""Deterministic enforcement of the short-term role's negative-FCF risk policy."""

from __future__ import annotations

import math


NEGATIVE_FCF_WARNING = "注意：自由現金流為負，短線財務壓力升高"
FINANCIAL_RISK_POLICY_VERSION = "negative-fcf:v1"


def enforce_trade_financial_risk(structured: dict, data: dict) -> dict:
    """Raise risk on the canonical raw TWD fact, without inventing its period.

    The prompt exposes this value as cash_flow.free_cash_flow_billion_twd.
    Inspect the unrounded raw fact so small negative values cannot round to zero.
    This policy never changes direction, prices, or source/completion validation.
    """
    raw = data.get("free_cash_flow_raw") if isinstance(data, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return structured
    try:
        value = float(raw)
    except (ValueError, OverflowError):
        return structured
    if not math.isfinite(value) or value >= 0:
        return structured
    catalyst = str(structured.get("core_catalyst") or "").strip()
    if NEGATIVE_FCF_WARNING not in catalyst:
        catalyst = f"{catalyst}；{NEGATIVE_FCF_WARNING}" if catalyst else NEGATIVE_FCF_WARNING
    return {**structured, "risk_level": "High", "core_catalyst": catalyst,
            "financial_risk_assessment": {
                "policy_version": FINANCIAL_RISK_POLICY_VERSION,
                "reason": "negative_free_cash_flow",
                "input_path": "data.free_cash_flow_raw", "value": value,
                "unit": "twd", "period": "not_verified",
            }}
