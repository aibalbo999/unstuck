"""Transparent component hypotheses with conditional tax class; never actual costs."""
from datetime import date
from statistics import mean
from cost_sensitivity import cost_sensitivity
from performance_evidence_quarantine import project_results


def evaluate_profiles(slots, policy):
    profiles = policy.get("profiles", [])
    classes = policy.get("instrument_classes", {})
    if not profiles or not policy.get("tax_rule_source") or not policy.get("as_of"):
        raise ValueError("explicit profiles, tax-rule source and as-of required")
    for profile in profiles:
        for key in ("commission_percent_each_side", "round_trip_slippage_bps", "short_borrow_financing_bps_per_calendar_day"):
            cost_sensitivity([], [profile[key]])  # Same finite/nonnegative/unknown boundary.
    rows = []
    exclusions = {}
    for slot in slots:
        old = slot.get("stored_result") or {}
        if slot.get("state") not in {"target_first", "stop_first", "horizon_exit"}:
            reason = slot.get("state") or "state_unknown"
        elif classes.get(slot.get("ticker")) not in {"equity_assumption", "equity_etf_0050_verified"}:
            reason = "instrument_tax_class_not_declared"
        elif old.get("trade_direction") not in {"Long", "Short"}:
            reason = "trade_direction_unknown"
        else:
            try:
                holding_days = (date.fromisoformat(old["exit_date"])-date.fromisoformat(old["entry_date"])).days
                if holding_days <= 0:
                    raise ValueError("same-day tax applicability not established")
                ratio = float(old["exit_price"])/float(old["entry_price"])
                cost_sensitivity([], [ratio])
                if ratio <= 0:
                    raise ValueError("nonpositive exit ratio")
                gross_check = cost_sensitivity([slot],[0])
                gross = gross_check["rows"][0]["gross_roi_pct"]
            except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
                reason = "gross_price_or_overnight_tax_context_unavailable"
            else:
                quarantined = project_results([old])[0].get("performance_evidence_status") == "quarantined"
                tax_rate = .1 if classes[slot["ticker"]] == "equity_etf_0050_verified" else .3
                tax_pct = tax_rate*(ratio if old["trade_direction"] == "Long" else 1)
                values = {}
                for profile in profiles:
                    commission_pct = float(profile["commission_percent_each_side"])*(1+ratio)
                    slip_pct = float(profile["round_trip_slippage_bps"])/100
                    borrow_pct = float(profile["short_borrow_financing_bps_per_calendar_day"])*holding_days/100 if old["trade_direction"] == "Short" else 0
                    total = commission_pct+tax_pct+slip_pct+borrow_pct
                    values[profile["id"]] = {"hypothetical_net_roi_pct":round(gross-total,6),
                        "commission_cost_pct":round(commission_pct,6),"conditional_tax_cost_pct":round(tax_pct,6),
                        "slippage_cost_pct":slip_pct,"borrow_financing_cost_pct":borrow_pct,"total_cost_pct":round(total,6)}
                rows.append({"ticker":slot.get("ticker"),"report_filename":slot.get("report_filename"),
                    "direction":old["trade_direction"],"holding_calendar_days":holding_days,
                    "tax_rate_pct":tax_rate,"tax_class":classes[slot["ticker"]],"saved_gross_roi_pct":gross,
                    "evidence_quarantined":quarantined,"profiles":values})
                continue
        exclusions[reason] = exclusions.get(reason,0)+1
    summaries = {}
    for label, subset in (("all_saved_illustration", rows), ("not_quarantined_conditional", [r for r in rows if not r["evidence_quarantined"]])):
        summary = {}
        for profile in profiles:
            values=[r["profiles"][profile["id"]]["hypothetical_net_roi_pct"] for r in subset]
            flipped=[r["ticker"] for r in subset if r["saved_gross_roi_pct"]>0 and r["profiles"][profile["id"]]["hypothetical_net_roi_pct"]<=0]
            summary[profile["id"]]={"count":len(values),"min_pct":min(values) if values else None,
                "max_pct":max(values) if values else None,"mean_pct":round(mean(values),6) if values else None,
                "positive_gross_to_nonpositive_net":flipped}
        summaries[label]=summary
    return {"status":"hypothetical_component_cost_sensitivity_only","policy":policy,"rows":rows,
        "input_slot_count":len(slots),"mature_gross_count":len(rows),"excluded_state_counts":exclusions,
        "evidence_quarantined_count":sum(r["evidence_quarantined"] for r in rows),"summaries":summaries,
        "validated_net_results":0,"actual_cost_verified":False,
        "limitations":["Saved gross price evidence may be wrong;quarantined rows are illustration only",
            "Equity class and overnight status are conditional scenario assumptions;0050 ETF class separately sourced",
            "Commission/slippage/borrow rates are explicit hypotheses,not actual broker costs",
            "No position size,minimum fees,rounding or actual fills modeled;no win-rate or strategy-validity claim"]}
