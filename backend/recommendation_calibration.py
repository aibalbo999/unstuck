"""Recommendation label calibration against target-return evidence."""

from __future__ import annotations

import re
from typing import Any

from price_parser import extract_price_numbers
from recommendation_labels import normalize_recommendation_label


BUY_MIN_RETURN_PCT = 10.0
HOLD_UPGRADE_RETURN_PCT = 30.0
BEARISH_POSITIVE_TARGET_PCT = 10.0
SHORT_MAX_RETURN_PCT = -15.0
HOLD_DOWNSIDE_PCT = -15.0
MIN_UPGRADE_CONFIDENCE = 6.0

LABEL_KEYS = ("recommendation", "建議")
CURRENT_PRICE_KEYS = ("current_price", "當日股價", "股價")
TARGET_12M_KEYS = ("target_12m", "長期目標（12個月）", "12個月目標", "12個月")
CONFIDENCE_KEYS = ("confidence", "信心指數", "信心")


def _first_value(mapping: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_key(mapping: dict, keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        if key in mapping:
            return key
    return fallback


def _parse_price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        numbers = extract_price_numbers(text)
    except (TypeError, ValueError):
        return None
    numbers = [number for number in numbers if number > 0]
    if not numbers:
        return None
    if _looks_like_price_range(text):
        range_numbers = _range_numbers(text)
        if len(range_numbers) >= 2:
            return sum(range_numbers[:2]) / 2
    return numbers[0]


def _looks_like_price_range(text: str) -> bool:
    return bool(re.search(r"\d\s*(?:-|~|～|至|到)\s*(?:NT\$?|NTD|TWD|新台幣|臺幣|台幣)?\s*\d", text))


def _range_numbers(text: str) -> list[float]:
    cleaned = re.sub(r"\d+(?:\.\d+)?\s*%", "", text)
    matches = re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", cleaned)
    return [float(match.replace(",", "")) for match in matches]


def _parse_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else None


def _expected_return_pct(target: float, current: float) -> float:
    return round((target / current - 1) * 100, 1)


def _can_upgrade(data_trust_status: str, confidence: float | None, analysis_text_stale: bool) -> bool:
    return (
        data_trust_status == "fresh"
        and not analysis_text_stale
        and confidence is not None
        and confidence >= MIN_UPGRADE_CONFIDENCE
    )


def calibrate_recommendation_summary(
    recommendation: dict,
    *,
    data_trust: dict | None = None,
    analysis_text_stale: bool = False,
    pipeline_id: str = "",
) -> dict:
    """Return a recommendation summary calibrated to target-return evidence.

    The original AI label is retained when a hard adjustment is made. Ambiguous
    cases are marked as watch instead of auto-upgraded, especially when data
    trust is not fresh.
    """
    if not isinstance(recommendation, dict):
        return {}

    calibrated = dict(recommendation)
    label_key = _first_key(calibrated, LABEL_KEYS, "recommendation")
    original_label = normalize_recommendation_label(_first_value(calibrated, LABEL_KEYS))
    if original_label == "N/A":
        return calibrated
    if str(pipeline_id or "").lower() == "v3":
        calibrated[label_key] = original_label
        for key in LABEL_KEYS:
            if key in calibrated:
                calibrated[key] = original_label
        return calibrated

    current_price = _parse_price(_first_value(calibrated, CURRENT_PRICE_KEYS))
    target_12m = _parse_price(_first_value(calibrated, TARGET_12M_KEYS))
    if current_price is None or current_price <= 0 or target_12m is None:
        return calibrated

    data_trust_status = str((data_trust or {}).get("status") or "unknown")
    confidence = _parse_confidence(_first_value(calibrated, CONFIDENCE_KEYS))
    expected_return = _expected_return_pct(target_12m, current_price)
    new_label = original_label
    status = "ok"
    reasons: list[str] = []

    if original_label in {"放空", "避免"} and expected_return > BEARISH_POSITIVE_TARGET_PCT:
        new_label = "持有"
        status = "adjusted"
        reasons.append(
            f"方向矛盾：原建議「{original_label}」但 12 個月目標價隱含 {expected_return:.1f}% 上行，先校準為持有並要求重審。"
        )
    elif original_label == "放空" and expected_return > SHORT_MAX_RETURN_PCT:
        new_label = "避免" if expected_return <= 0 else "持有"
        status = "adjusted"
        reasons.append(
            f"放空幅度不足：12 個月目標價僅隱含 {expected_return:.1f}% 報酬，未達放空門檻。"
        )
    elif original_label == "買入" and expected_return < BUY_MIN_RETURN_PCT:
        new_label = "持有"
        status = "adjusted"
        reasons.append(
            f"買入上行不足：12 個月目標價僅隱含 {expected_return:.1f}% 報酬，低於買入門檻。"
        )
    elif original_label == "持有" and expected_return >= HOLD_UPGRADE_RETURN_PCT:
        if _can_upgrade(data_trust_status, confidence, analysis_text_stale):
            new_label = "買入"
            status = "adjusted"
            reasons.append(
                f"上行空間充足：12 個月目標價隱含 {expected_return:.1f}% 報酬，且資料可信度與信心分數支援升格。"
            )
        else:
            status = "watch"
            reasons.append(
                f"12 個月目標價隱含 {expected_return:.1f}% 上行，但資料可信度、信心分數或 stale 狀態不足以自動升格。"
            )
    elif original_label == "持有" and expected_return <= HOLD_DOWNSIDE_PCT:
        if _can_upgrade(data_trust_status, confidence, analysis_text_stale):
            new_label = "避免"
            status = "adjusted"
            reasons.append(
                f"下行空間明顯：12 個月目標價隱含 {expected_return:.1f}% 報酬，校準為避免。"
            )
        else:
            status = "watch"
            reasons.append(
                f"12 個月目標價隱含 {expected_return:.1f}% 下行，但資料可信度、信心分數或 stale 狀態不足以自動降級。"
            )

    calibration = {
        "status": status,
        "original_recommendation": original_label,
        "calibrated_recommendation": new_label,
        "expected_return_pct": expected_return,
        "current_price": round(current_price, 4),
        "target_12m": round(target_12m, 4),
        "data_trust_status": data_trust_status,
        "confidence_score": confidence,
        "analysis_text_stale": bool(analysis_text_stale),
        "reasons": reasons,
    }
    calibrated["recommendation_calibration"] = calibration

    if new_label != original_label:
        calibrated["original_recommendation"] = original_label
        calibrated[label_key] = new_label
        for key in LABEL_KEYS:
            if key in calibrated:
                calibrated[key] = new_label

    return calibrated
