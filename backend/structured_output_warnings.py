"""Structured-output quality warning helpers."""

from __future__ import annotations

from confidence_calibration import (
    build_confidence_calibration,
    confidence_downgrade_warning,
    confidence_score,
    has_unresolved_cross_source_conflict,
)
from report_freshness_summary import safe_bool


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def _confidence_text(score: float) -> str:
    value = float(score)
    return f"{int(value) if value.is_integer() else value:g}/10"


def calibrate_structured_confidence(agent_num: int, structured: dict, context: dict) -> dict:
    """Apply the deterministic trust cap to the user-visible final confidence."""
    if agent_num not in {7, 16, 19}:
        return {}
    recommendation = structured.get("recommendation")
    if not isinstance(recommendation, dict):
        return {}
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
    circuit_ever_opened = safe_bool((context.get("circuit_breaker") or {}).get("_ever_opened", False))
    calibration = build_confidence_calibration(
        recommendation,
        data.get("data_trust", {}),
        circuit_ever_opened,
        has_unresolved_cross_source_conflict(data),
    )
    original_score = calibration.get("original_score", calibration.get("confidence_score"))
    effective_score = calibration.get("confidence_score")
    cap = calibration.get("max_recommended_confidence")
    if not all(isinstance(value, (int, float)) for value in (original_score, effective_score, cap)):
        context["confidence_calibration"] = calibration
        return calibration

    applied_score = min(float(effective_score), float(cap))
    if applied_score >= float(original_score):
        context["confidence_calibration"] = calibration
        return calibration

    confidence_key = next(
        (key for key in recommendation if key == "confidence" or "信心" in str(key)),
        "信心指數",
    )
    original_text = str(recommendation.get(confidence_key) or "N/A")
    recommendation[confidence_key] = _confidence_text(applied_score)
    adjusted = {
        **calibration,
        "status": "adjusted",
        "raw_confidence": original_text,
        "original_score": float(original_score),
        "applied_score": applied_score,
        "confidence_score": applied_score,
    }
    structured["confidence_calibration"] = {
        "status": "adjusted",
        "original_confidence": original_text,
        "applied_confidence": recommendation[confidence_key],
        "data_trust_status": adjusted.get("data_trust_status", "unknown"),
        "reasons": list(adjusted.get("reasons") or []),
    }
    context["confidence_calibration"] = adjusted
    context.setdefault("confidence_adjustments", []).append({
        "agent_num": agent_num,
        "original_confidence": original_text,
        "applied_confidence": recommendation[confidence_key],
        "reasons": list(calibration.get("reasons") or []),
    })
    return adjusted


def warn_high_confidence_with_low_trust(agent_num: int, structured: dict, context: dict) -> None:
    if agent_num not in {7, 16, 19}:
        return
    calibration = calibrate_structured_confidence(agent_num, structured, context)
    warning = confidence_downgrade_warning(agent_num, calibration)
    if warning:
        context.setdefault("structured_quality_warnings", []).append(warning)


_confidence_score = confidence_score
_warn_high_confidence_with_low_trust = warn_high_confidence_with_low_trust
