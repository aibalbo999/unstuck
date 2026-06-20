"""DCF consistency checks shared by the final audit."""

from __future__ import annotations

from validators import _extract_price_numbers, strip_generated_audit_sections


def dcf_conflict_warnings(analyses: dict, data: dict) -> list[str]:
    text = strip_generated_audit_sections(str((analyses or {}).get(4, "")))
    if "DCF" not in text.upper():
        return []

    quant_metrics = data.get("quant_metrics", {}) if isinstance(data.get("quant_metrics"), dict) else {}
    prices = _extract_price_numbers(text)
    if not prices:
        return []

    scenarios = _quant_dcf_scenarios(quant_metrics)
    if scenarios and len(prices) >= 3:
        warnings = []
        for index, (scenario, label) in enumerate((
            ("bear", "熊市情境"),
            ("base", "基本情境"),
            ("bull", "牛市情境"),
        )):
            quant_dcf = scenarios.get(scenario)
            agent_price = float(prices[index])
            if not quant_dcf or agent_price <= 0:
                continue
            gap = abs(agent_price - quant_dcf) / max(agent_price, quant_dcf)
            if gap > 0.30:
                warnings.append(
                    f"DCF 來源衝突（{label}）：Agent 4 目標價 NT${agent_price:g} "
                    f"與系統情境 DCF NT${quant_dcf:g} 差距超過 30%，應說明假設差異。"
                )
        return warnings

    try:
        quant_dcf = float(quant_metrics.get("dcf_intrinsic_value"))
    except (TypeError, ValueError):
        return []
    if quant_dcf <= 0:
        return []

    agent_price = float(prices[0])
    if agent_price <= 0:
        return []
    gap = abs(agent_price - quant_dcf) / max(agent_price, quant_dcf)
    if gap <= 0.30:
        return []

    return [
        "DCF 來源衝突：Agent 4 DCF/目標價 "
        f"NT${agent_price:g} 與系統 quant_metrics DCF NT${quant_dcf:g} 差距超過 30%，"
        "應選一為準並說明差異原因。"
    ]


def _quant_dcf_scenarios(quant_metrics: dict) -> dict[str, float]:
    raw = quant_metrics.get("dcf_scenarios")
    if not isinstance(raw, dict):
        calculations = quant_metrics.get("calculations") if isinstance(quant_metrics.get("calculations"), dict) else {}
        default = calculations.get("dcf_scenarios_default") if isinstance(calculations, dict) else {}
        raw = default.get("scenarios") if isinstance(default, dict) else {}
    values = {}
    for scenario in ("bear", "base", "bull"):
        row = raw.get(scenario) if isinstance(raw, dict) else None
        if not isinstance(row, dict):
            continue
        value = row.get("intrinsic_value", row.get("price_per_share_twd"))
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            values[scenario] = number
    return values
