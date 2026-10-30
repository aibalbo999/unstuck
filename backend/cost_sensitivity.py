"""Hypothetical sensitivity of mature saved gross results, never validated net P&L."""
import math


def cost_sensitivity(slots, round_trip_cost_bps):
    costs = []
    for value in round_trip_cost_bps:
        if isinstance(value, bool):
            raise ValueError("cost scenarios must be finite nonnegative basis points")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("cost scenarios must be finite nonnegative basis points") from None
        if not math.isfinite(number) or number < 0:
            raise ValueError("cost scenarios must be finite nonnegative basis points")
        costs.append(number)
    if not costs:
        raise ValueError("explicit hypothetical scenarios required;unknown costs cannot default to zero")
    rows, exclusions = [], {}
    for slot in slots:
        old = slot.get("stored_result") or {}
        if slot.get("state") not in {"target_first", "stop_first", "horizon_exit"}:
            reason = slot.get("state") or "state_unknown"
        else:
            try:
                value = old.get("strategy_roi_pct")
                gross = float(value)
                if isinstance(value, bool) or not math.isfinite(gross):
                    raise ValueError
            except (TypeError, ValueError):
                reason = "gross_return_unavailable"
            else:
                rows.append({"ticker":slot.get("ticker"),"report_filename":slot.get("report_filename"),
                    "gross_roi_pct":gross,"hypothetical_net_roi_pct":{str(c):round(gross-c/100,6) for c in costs},
                    "price_basis_verified":isinstance(old.get("price_comparability"),dict) and old["price_comparability"].get("status")=="verified"})
                continue
        exclusions[reason] = exclusions.get(reason,0) + 1
    return {"status":"hypothetical_cost_sensitivity_only","input_slot_count":len(slots),
            "mature_executed_gross_count":len(rows),"excluded_state_counts":exclusions,
            "round_trip_cost_bps":costs,"cost_unit":"basis_points_of_entry_notional;round_trip_total",
            "formula":"hypothetical_net_roi_pct = saved_gross_roi_pct - cost_bps / 100",
            "cost_origin":"caller_declared_hypothetical;not_fee_quote_or_observed_fills",
            "validated_net_results":0,"actual_cost_verified":False,"rows":rows,
            "limitation":"Conditional arithmetic on possibly unverified saved gross prices;does not repair price/PIT evidence, establish strategy validity, or represent actual commissions/tax/slippage/borrow costs."}
