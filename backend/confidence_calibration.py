"""Calibrate report confidence against recorded data trust."""

from __future__ import annotations

from typing import Any, Optional

from confidence_score_parser import parse_confidence_score_text
from data_trust_scoring import normalize_data_trust, trust_status_label


TRUST_CONFIDENCE_CAPS = {
    "fresh": 10,
    "partial": 7,
    "stale": 7,
    "unknown": 6,
    "error": 5,
}


def confidence_score(value: Any) -> Optional[float]:
    return parse_confidence_score_text(value)


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


def build_confidence_calibration(
    recommendation: dict,
    data_trust: Any,
    circuit_ever_opened: bool = False,
    has_unresolved_conflict: bool = False,
) -> dict:
    trust = normalize_data_trust(data_trust)
    trust_status = str(trust.get("status") or "unknown")
    cap = confidence_cap_for_trust(trust_status)
    if circuit_ever_opened and cap > 8:
        cap = 8
        circuit_note = "資料驗證過程曾觸發修復機制，信心上限降至 8/10。"
    else:
        circuit_note = None
    if has_unresolved_conflict and cap > 6:
        cap = 6
        conflict_note = "跨來源資料仍存在未解衝突，信心上限降至 6/10。"
    else:
        conflict_note = None
    raw_confidence = confidence_value(recommendation)
    score = confidence_score(raw_confidence)

    basis = recommendation.get("confidence_basis") or {}
    evidence_items = basis.get("evidence_items", []) if isinstance(basis, dict) else []
    risks = basis.get("key_risks_acknowledged", []) if isinstance(basis, dict) else []

    penalty = 0
    penalty_reasons = []

    if isinstance(basis, dict) and basis:
        if len(evidence_items) < 3:
            penalty += 2
            penalty_reasons.append(f"佐證數量不足（{len(evidence_items)} < 3），信心強制下調。")
        if len(risks) < 2:
            penalty += 1
            penalty_reasons.append(f"風險考量不足（{len(risks)} < 2），信心強制下調。")

    if score is None:
        return {
            "status": "unavailable",
            "raw_confidence": raw_confidence or "N/A",
            "confidence_score": None,
            "data_trust_status": trust_status,
            "data_trust_label": trust_status_label(trust_status),
            "max_recommended_confidence": cap,
            "reasons": ["未解析到信心分數，無法校準。"],
            "circuit_ever_opened": circuit_ever_opened,
            "has_unresolved_conflict": has_unresolved_conflict,
        }

    effective_score = max(1, score - penalty)

    if effective_score > cap:
        status = "needs_downgrade"
        reasons = [
            f"data_trust={trust_status} 時建議信心上限 {cap}/10，但報告信心為 {raw_confidence}。"
        ] + penalty_reasons
    elif trust_status == "fresh":
        status = "aligned" if not penalty_reasons else "calibrated"
        reasons = ["核心資料新鮮，信心分數未受資料可信度降級。"] + penalty_reasons
    else:
        status = "calibrated"
        reasons = [
            f"data_trust={trust_status} 時信心分數未高於建議上限 {cap}/10。"
        ] + penalty_reasons
    if circuit_note is not None:
        reasons.insert(0, circuit_note)
    if conflict_note is not None:
        reasons.insert(0, conflict_note)

    return {
        "status": status,
        "raw_confidence": raw_confidence,
        "confidence_score": effective_score,
        "original_score": score,
        "data_trust_status": trust_status,
        "data_trust_label": trust_status_label(trust_status),
        "max_recommended_confidence": cap,
        "reasons": reasons,
        "circuit_ever_opened": circuit_ever_opened,
        "has_unresolved_conflict": has_unresolved_conflict,
    }


def has_unresolved_cross_source_conflict(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    cross_validation = data.get("cross_validation")
    if not isinstance(cross_validation, dict):
        return False
    if str(cross_validation.get("overall_verdict") or "").lower() == "conflict":
        return True
    return bool(cross_validation.get("conflict_fields"))
