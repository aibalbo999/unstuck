"""DCF consistency checks shared by the final audit."""

from __future__ import annotations

from validators import _extract_price_numbers, strip_generated_audit_sections


def dcf_conflict_warnings(analyses: dict, data: dict) -> list[str]:
    text = strip_generated_audit_sections(str((analyses or {}).get(4, "")))
    if "DCF" not in text.upper():
        return []

    quant_metrics = data.get("quant_metrics", {}) if isinstance(data.get("quant_metrics"), dict) else {}
    try:
        quant_dcf = float(quant_metrics.get("dcf_intrinsic_value"))
    except (TypeError, ValueError):
        return []
    if quant_dcf <= 0:
        return []

    prices = _extract_price_numbers(text)
    if not prices:
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
