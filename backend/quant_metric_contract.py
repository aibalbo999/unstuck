"""Shared calculation contract and read-only DCF availability projection."""

from __future__ import annotations

from mapping_fields import safe_mapping_dict
from quant_input_contract import finite_number, read_quant_inputs, wacc_policy

CONTRACT_VERSION = "quant_metrics.v2"
DCF_METHOD = "fcf_dcf"
FACT_FALLBACK_FIELDS = {
    "total_equity", "total_debt", "total_cash", "free_cash_flows", "shares_outstanding",
    "market_cap_raw", "total_debt_raw", "total_cash_raw", "free_cash_flow_raw", "shares_raw",
}


def metric_status(reasons):
    return {"status": "unavailable" if reasons else "available", "reason_codes": list(dict.fromkeys(reasons))}


def calculate_quant_contract(data, *, wacc_calculator, scenario_builder, dcf_calculator):
    data = safe_mapping_dict(data) or {}
    facts, provenance, reasons = read_quant_inputs(data)
    policy = wacc_policy(data)
    calculations, scenarios = {}, {}
    wacc = None
    if not reasons["wacc"]:
        computed = wacc_calculator(
            facts["market_cap_raw"], facts["total_debt_raw"],
            policy["cost_of_equity_pct"], policy["cost_of_debt_pct"], policy["tax_rate_pct"],
        )
        pct = finite_number(computed.get("wacc_pct"))
        if pct is not None and pct > 0:
            wacc = pct / 100
            calculations["market_value_wacc_default"] = computed
        else:
            reasons["wacc"].append("wacc_calculation_unavailable")
            reasons["dcf"].append("wacc_calculation_unavailable")

    revenue = data.get("revenue_history")
    growth = None
    if isinstance(revenue, (list, tuple)) and len(revenue) >= 2:
        prev, latest = finite_number(revenue[-2]), finite_number(revenue[-1])
        if prev is not None and prev > 0 and latest is not None and latest > 0:
            growth = finite_number((latest / prev - 1) * 100)
            provenance["revenue_growth"] = {"path": "data.revenue_history[-2:]", "unit": "billion_twd", "value": [prev, latest]}
    base_fcf = facts["base_fcf_billion_twd"]
    base_note = "latest available FCF"
    income = data.get("net_income_history")
    latest_income = finite_number(income[-1]) if isinstance(income, (list, tuple)) and income else None
    fcf_history = data.get("fcf_history")
    fcf_index = next((i for i in range(len(fcf_history) - 1, -1, -1) if finite_number(fcf_history[i]) is not None), None) if isinstance(fcf_history, (list, tuple)) else None
    history_fcf = finite_number(fcf_history[fcf_index]) if fcf_index is not None else None
    if base_fcf is not None and base_fcf > 0 and latest_income is not None and latest_income > 0 and growth is not None and growth > 50 and history_fcf is not None and history_fcf / latest_income > 1:
        provenance["normalization_net_income"] = {"path": "data.net_income_history[-1]", "unit": "billion_twd", "value": latest_income}
        provenance["normalization_fcf"] = {"path": f"data.fcf_history[{fcf_index}]", "unit": "billion_twd", "value": history_fcf}
        base_fcf = max(min(base_fcf, latest_income * 0.8), 0.01)
        base_note = "normalized to 80% of latest annual net income because high growth plus FCF/net income > 100% is not treated as steady state"
    if not reasons["dcf"]:
        dcf = scenario_builder(
            base_fcf_billion_twd=base_fcf, base_fcf_note=base_note,
            latest_revenue_growth_pct=growth, wacc_pct=wacc * 100,
            shares_outstanding=facts["shares_raw"],
            net_debt_billion_twd=(facts["total_debt_raw"] - facts["total_cash_raw"]) / 1e9,
            dcf_calculator=dcf_calculator,
        )
        for name, row in dcf["scenarios"].items():
            value = finite_number(row.get("price_per_share_twd"))
            if value is None or value <= 0:
                reasons["dcf"].append("dcf_non_positive_or_invalid_equity_value")
                break
            scenarios[name] = {**row, "intrinsic_value": value, "scenario": name,
                               "method": DCF_METHOD, "unit": "twd_per_share",
                               "wacc": row["wacc_pct"] / 100,
                               "terminal_growth_rate": row["terminal_growth_pct"] / 100}
        if reasons["dcf"]:
            scenarios = {}
        else:
            calculations["dcf_scenarios_default"] = {**dcf, "method": DCF_METHOD, "unit": "twd_per_share", "scenarios": scenarios}
    intrinsic = scenarios.get("base", {}).get("intrinsic_value")
    price = facts["current_price"]
    margin = finite_number((intrinsic - price) / intrinsic) if intrinsic is not None and price is not None and price > 0 else None
    pe = finite_number(price / facts["eps"]) if not reasons["implied_pe"] else None
    if not reasons["implied_pe"] and pe is None:
        reasons["implied_pe"].append("implied_pe_non_finite")
    result = {
        "contract_version": CONTRACT_VERSION,
        "metric_status": {name: metric_status(codes) for name, codes in reasons.items()},
        "input_provenance": provenance,
        "unit_contract": {"money": "billion_twd", "percent": "percentage_points", "price": "twd_per_share", "wacc_computed": "ratio"},
        "calculation_methods": {"dcf": DCF_METHOD, "wacc": "market_value_wacc", "implied_pe": "price_over_eps"},
        "assumptions": {"wacc": policy, "dcf": {"kind": "assumption", "policy": "financial_dcf_scenarios", "base_fcf_note": base_note, "latest_revenue_growth_pct": growth}},
        "wacc_assumptions": policy, "calculations": calculations,
        "wacc_computed": wacc, "dcf_intrinsic_value": intrinsic, "dcf_scenarios": scenarios,
        "implied_pe_ratio": round(pe, 2) if pe is not None else None,
        "margin_of_safety": round(margin, 4) if margin is not None else None,
        "fallback_fields": [], "note": "僅可用指標可引用；事實來源與估值政策假設分開記錄。",
    }
    warning = quant_unavailability_message(result)
    if warning:
        result["data_quality_warning"] = warning
    return result


def dcf_availability(quant):
    if not isinstance(quant, dict):
        return metric_status(["quant_metrics_missing"])
    if quant.get("contract_version") != CONTRACT_VERSION:
        fields = quant.get("fallback_fields")
        if isinstance(fields, (list, tuple)) and any(isinstance(f, str) and f in FACT_FALLBACK_FIELDS for f in fields):
            return metric_status(["legacy_fact_fallback"])
        return metric_status(["legacy_contract_unverified"])
    statuses = quant.get("metric_status")
    status = statuses.get("dcf") if isinstance(statuses, dict) else None
    if not isinstance(status, dict) or status.get("status") != "available" or status.get("reason_codes"):
        return metric_status(status.get("reason_codes") or ["dcf_unavailable"]) if isinstance(status, dict) else metric_status(["dcf_status_missing"])
    units = quant.get("unit_contract")
    methods = quant.get("calculation_methods")
    if not isinstance(units, dict) or units.get("price") != "twd_per_share":
        return metric_status(["dcf_unit_unverified"])
    if not isinstance(methods, dict) or methods.get("dcf") != DCF_METHOD or not _valid_dcf_provenance(quant.get("input_provenance")):
        return metric_status(["dcf_method_or_provenance_unverified"])
    return metric_status([])


def _valid_dcf_provenance(provenance):
    if not isinstance(provenance, dict):
        return False
    for field in ("market_cap_raw", "total_debt_raw", "total_cash_raw", "shares_raw", "free_cash_flow_raw"):
        row = provenance.get(field)
        if not isinstance(row, dict):
            return False
        value = finite_number(row.get("value"))
        if value is None or value < 0 or (field not in {"total_debt_raw", "total_cash_raw"} and value == 0):
            return False
        expected_unit = "shares" if field == "shares_raw" else "twd"
        history = field == "free_cash_flow_raw" and isinstance(row.get("path"), str) and row["path"].startswith("data.fcf_history[") and row.get("unit") == "billion_twd"
        if not history and (row.get("path") != f"data.{field}" or row.get("unit") != expected_unit):
            return False
    return True


def trusted_dcf_scenarios(quant):
    if dcf_availability(quant)["status"] != "available":
        return {}
    raw = quant.get("dcf_scenarios")
    if not isinstance(raw, dict):
        return {}
    rows = {}
    for name in ("bear", "base", "bull"):
        row = raw.get(name)
        if not isinstance(row, dict) or row.get("method") != DCF_METHOD or row.get("unit") != "twd_per_share" or row.get("scenario") != name:
            continue
        value = finite_number(row.get("intrinsic_value"))
        if value is not None and value > 0:
            rows[name] = row
    return rows


def quant_unavailability_message(quant):
    if not isinstance(quant, dict):
        return ""
    statuses = quant.get("metric_status")
    labels = {"dcf": "DCF", "wacc": "WACC", "implied_pe": "本益比"}
    messages = []
    if quant.get("contract_version") == CONTRACT_VERSION and isinstance(statuses, dict):
        for metric, label in labels.items():
            status = statuses.get(metric)
            if isinstance(status, dict) and status.get("status") == "unavailable":
                codes = status.get("reason_codes")
                codes = [code for code in codes if isinstance(code, str)] if isinstance(codes, list) else []
                messages.append(f"{label} 不可用：" + "、".join(codes))
    elif dcf_availability(quant)["reason_codes"] == ["legacy_fact_fallback"]:
        messages.append("目前規則：DCF 不可用；歷史記錄曾使用缺失財務事實的預設值，未重新驗證。")
    elif quant.get("contract_version") != CONTRACT_VERSION and (isinstance(quant.get("dcf_scenarios"), dict) or finite_number(quant.get("dcf_intrinsic_value")) is not None):
        messages.append("歷史 DCF 未依目前契約驗證；保留當時數值，不代表目前可信計算來源。")
    return "；".join(messages)
