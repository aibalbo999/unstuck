"""Fail closed when an executable plan cannot be compared with raw OHLC."""
from reporting.trade_price_grid import grid_assessment
import math


def assess_price_comparability(context, bars):
    context = context if isinstance(context, dict) else {}
    data, setup = context.get("data", {}), context.get("setup", {})
    if str(data.get("ticker") or "").endswith(".TWO"):
        return {"status": "unverified", "reason": "tpex_price_grid_not_verified"}
    grid = grid_assessment(data, setup)
    if grid["status"] != "grid_aligned_analysis_levels":
        return {"status": "unverified", "reason": "off_grid_or_unknown_instrument", "price_grid": grid}
    basis = setup.get("price_basis") or data.get("daily_market_data", {}).get("price_adjustment_basis")
    if basis not in {"unadjusted_exchange_ohlc", "unadjusted_provider_ohlc"}:
        return {"status": "unverified", "reason": "plan_price_basis_unverified", "recorded_basis": basis}
    if not bars or any("stock_splits" not in row or "dividends" not in row for row in bars):
        return {"status": "unverified", "reason": "corporate_actions_coverage_unknown"}
    for row in bars:
        for key in ("stock_splits", "dividends"):
            value = row[key]
            if isinstance(value, bool):
                return {"status": "unverified", "reason": "corporate_actions_coverage_unknown"}
            try:
                if not math.isfinite(float(value)) or float(value) < 0:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                return {"status": "unverified", "reason": "corporate_actions_coverage_unknown"}
    if any(float(row["stock_splits"]) != 0 or float(row["dividends"]) != 0 for row in bars):
        return {"status": "unverified", "reason": "corporate_action_requires_rebased_plan"}
    if any(row.get("observation_provenance", {}).get("price_basis") == "provider_ohlc_auto_adjust_false" for row in bars):
        return {"status": "unverified", "reason": "provider_raw_basis_not_established",
                "limitation": "auto_adjust=False alone cannot establish exchange-raw historical split prices."}
    return {"status": "verified", "reason": "raw_basis_grid_and_no_actions_verified", "price_grid": grid}


def assess_cost_evidence(context, transaction_cost):
    import math
    setup = (context or {}).get("setup", {})
    components = setup.get("transaction_cost_components")
    required = ("commission", "transaction_tax", "slippage")
    if setup.get("trade_direction") == "Short":
        required += ("borrow_and_financing",)
    if not isinstance(components, dict) or not components.get("source") or not components.get("as_of") or components.get("unit") != "round_trip_per_share":
        return {"status": "unverified", "reason": "missing_round_trip_cost_components_or_provenance"}
    try:
        values = [float(components[key]) for key in required]
        total = float(transaction_cost)
        if not all(math.isfinite(v) and v >= 0 for v in [*values, total]) or abs(sum(values) - total) > 1e-8:
            raise ValueError
    except (KeyError, ValueError, TypeError):
        return {"status": "unverified", "reason": "invalid_or_inconsistent_cost_components"}
    return {"status": "complete_declared_assumptions", "total": total,
            "limitation": "Recorded cost assumptions, not observed fills or independently certified actual costs."}
