"""Structured-output quality warning helpers."""

from __future__ import annotations

from confidence_calibration import (
    build_confidence_calibration,
    confidence_downgrade_warning,
    confidence_score,
    has_unresolved_cross_source_conflict,
)


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
    warning = confidence_downgrade_warning(agent_num, calibration)
    if warning:
        context.setdefault("structured_quality_warnings", []).append(warning)


_confidence_score = confidence_score
_warn_high_confidence_with_low_trust = warn_high_confidence_with_low_trust
