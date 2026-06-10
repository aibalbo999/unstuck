"""Calibrate report confidence against recorded data trust."""

from __future__ import annotations

import re
from typing import Any, Optional

from data_trust_scoring import normalize_data_trust, trust_status_label


TRUST_CONFIDENCE_CAPS = {
    "fresh": 10,
    "partial": 7,
    "stale": 7,
    "unknown": 6,
    "error": 5,
}


def confidence_score(value: Any) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return None
    score = float(match.group(1))
    if score <= 1:
        return round(score * 10, 2)
    return round(score, 2)


def confidence_value(recommendation: dict) -> str:
    if not isinstance(recommendation, dict):
        return ""
    for key, value in recommendation.items():
        key_text = str(key)
        if key_text == "confidence" or "信心" in key_text:
            return str(value)
    nested = recommendation.get("recommendation")
    if isinstance(nested, dict):
        return confidence_value(nested)
    return ""


def confidence_cap_for_trust(status: str) -> int:
    return TRUST_CONFIDENCE_CAPS.get(str(status or "unknown"), TRUST_CONFIDENCE_CAPS["unknown"])


def build_confidence_calibration(recommendation: dict, data_trust: Any) -> dict:
    trust = normalize_data_trust(data_trust)
    trust_status = str(trust.get("status") or "unknown")
    cap = confidence_cap_for_trust(trust_status)
    raw_confidence = confidence_value(recommendation)
    score = confidence_score(raw_confidence)

    if score is None:
        return {
            "status": "unavailable",
            "raw_confidence": raw_confidence or "N/A",
            "confidence_score": None,
            "data_trust_status": trust_status,
            "data_trust_label": trust_status_label(trust_status),
            "max_recommended_confidence": cap,
            "reasons": ["未解析到信心分數，無法校準。"],
        }

    if score > cap:
        status = "needs_downgrade"
        reasons = [
            f"data_trust={trust_status} 時建議信心上限 {cap}/10，但報告信心為 {raw_confidence}。"
        ]
    elif trust_status == "fresh":
        status = "aligned"
        reasons = ["核心資料新鮮，信心分數未受資料可信度降級。"]
    else:
        status = "calibrated"
        reasons = [
            f"data_trust={trust_status} 時信心分數未高於建議上限 {cap}/10。"
        ]

    return {
        "status": status,
        "raw_confidence": raw_confidence,
        "confidence_score": score,
        "data_trust_status": trust_status,
        "data_trust_label": trust_status_label(trust_status),
        "max_recommended_confidence": cap,
        "reasons": reasons,
    }
