"""Structured-output quality warning helpers."""

from __future__ import annotations

from confidence_calibration import build_confidence_calibration, confidence_score, has_unresolved_cross_source_conflict


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def warn_high_confidence_with_low_trust(agent_num: int, structured: dict, context: dict) -> None:
    if agent_num not in {7, 16, 19}:
        return
    trust = context.get("data", {}).get("data_trust", {}) if isinstance(context.get("data"), dict) else {}
    circuit_ever_opened = bool((context.get("circuit_breaker") or {}).get("_ever_opened", False))
    calibration = build_confidence_calibration(
        structured.get("recommendation", {}) or {},
        trust,
        circuit_ever_opened,
        has_unresolved_cross_source_conflict(context.get("data", {}) if isinstance(context.get("data"), dict) else {}),
    )
    context["confidence_calibration"] = calibration
    if calibration.get("status") != "needs_downgrade":
        return
    status = calibration.get("data_trust_status", "unknown")
    confidence = calibration.get("raw_confidence", "N/A")
    cap = calibration.get("max_recommended_confidence")
    context.setdefault("structured_quality_warnings", []).append(
        f"Agent {agent_num} 在 data_trust={status} 時給出高信心（{confidence}），建議信心上限 {cap}/10，需於報告中明確說明資料限制。"
    )


_confidence_score = confidence_score
_warn_high_confidence_with_low_trust = warn_high_confidence_with_low_trust
