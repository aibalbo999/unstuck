"""Deterministic content-credibility checks for rendered reports."""

from __future__ import annotations

from typing import Any

from data_trust_scoring import normalize_data_trust, trust_status_label
from price_parser import extract_price_numbers
from recommendation_labels import normalize_recommendation_label
from report_reproducibility import (
    EXPLICIT_TARGET_PRICE_MIN_SCORE,
    data_confidence_score,
    detect_explicit_target_price_fields,
)


BUY_TARGET_MIN_UPSIDE_PCT = 0.0
BEARISH_TARGET_MAX_UPSIDE_PCT = 10.0
HOLD_EXTREME_MOVE_PCT = 30.0
HIGH_CONFIDENCE_MIN_SCORE = 8.0


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _issue(issue_id: str, message: str, details: dict | None = None) -> dict:
    issue = {"id": issue_id, "message": message}
    if details:
        issue["details"] = details
    return issue


def _check(check_id: str, status: str, message: str, details: dict | None = None) -> dict:
    result = {"id": check_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def _first_value_by_key_fragment(values: dict, fragment: str) -> Any:
    for key, value in values.items():
        if fragment in str(key):
            return value
    return None


def _first_price(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        prices = extract_price_numbers(str(value))
    except (TypeError, ValueError):
        return None
    return float(prices[0]) if prices else None


def _target_price_candidates(parsed: dict) -> list[dict]:
    recommendation = _as_dict(parsed.get("recommendation"))
    price_targets = _as_dict(parsed.get("price_targets"))
    candidates: list[dict] = []
    for label in ("12個月", "6個月", "3個月"):
        value = _first_value_by_key_fragment(recommendation, label)
        price = _first_price(value)
        if price is not None:
            candidates.append({"source": f"recommendation.{label}", "label": label, "price": price, "raw": value})
    for label in ("基本情境", "牛市情境", "熊市情境"):
        value = price_targets.get(label)
        price = _first_price(value)
        if price is not None:
            candidates.append({"source": f"price_targets.{label}", "label": label, "price": price, "raw": value})
    if not candidates:
        for label, value in price_targets.items():
            price = _first_price(value)
            if price is not None:
                candidates.append({"source": f"price_targets.{label}", "label": str(label), "price": price, "raw": value})
    return candidates


def _main_target_price(parsed: dict) -> dict | None:
    candidates = _target_price_candidates(parsed)
    return candidates[0] if candidates else None


def _confidence_score(recommendation: dict) -> float | None:
    value = _first_value_by_key_fragment(recommendation, "信心")
    if value is None:
        return None
    try:
        numbers = extract_price_numbers(str(value))
    except (TypeError, ValueError):
        return None
    if not numbers:
        return None
    score = float(numbers[0])
    if score > 10:
        return min(10.0, score / 10.0)
    return score


def _upside_pct(target_price: float, current_price: float) -> float:
    if current_price <= 0:
        return 0.0
    return (target_price - current_price) / current_price * 100


def _evidence_exit_gate(context: dict, snapshot: dict) -> dict:
    return _as_dict(snapshot.get("evidence_exit_gate")) or _as_dict(context.get("evidence_exit_gate"))


def _evidence_matrix_rows(context: dict, snapshot: dict) -> list:
    if "evidence_matrix" in snapshot:
        return _as_list(snapshot.get("evidence_matrix"))
    try:
        from .evidence_matrix import build_evidence_matrix_rows

        return build_evidence_matrix_rows(context)
    except Exception:
        return []


def _has_evidence_claim(rows: list, claim: str) -> bool:
    return any(isinstance(row, dict) and str(row.get("claim") or "") == claim for row in rows)


def evaluate_content_credibility(context: dict, snapshot: dict | None = None, markdown: str | None = None) -> dict:
    """Evaluate whether report conclusions are directionally credible against deterministic data."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    data = _as_dict(snapshot.get("data")) or _as_dict(context.get("data"))
    parsed = _as_dict(context.get("parsed"))
    recommendation = _as_dict(parsed.get("recommendation"))
    data_trust = normalize_data_trust(snapshot.get("data_trust") or data.get("data_trust"))
    current_price = _first_price(data.get("current_price"))
    recommendation_label = normalize_recommendation_label(_first_value_by_key_fragment(recommendation, "建議"))
    main_target = _main_target_price(parsed)
    evidence_gate = _evidence_exit_gate(context, snapshot)
    evidence_verdict = str(evidence_gate.get("verdict") or "not_recorded")
    confidence_score = _confidence_score(recommendation)
    explicit_target_fields = detect_explicit_target_price_fields(context)
    evidence_rows = _evidence_matrix_rows(context, snapshot)

    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if current_price and main_target:
        upside = _upside_pct(float(main_target["price"]), current_price)
        details = {
            "recommendation": recommendation_label,
            "current_price": current_price,
            "target_price": main_target["price"],
            "target_source": main_target["source"],
            "upside_pct": round(upside, 2),
        }
        if recommendation_label == "買入" and upside <= BUY_TARGET_MIN_UPSIDE_PCT:
            issue = _issue(
                "buy_target_below_current_price",
                "買入結論的主要目標價未高於目前股價。",
                details,
            )
            blocking.append(issue)
            checks.append(_check("recommendation_target_alignment", "blocked", issue["message"], details))
        elif recommendation_label in {"避免", "放空"} and upside >= BEARISH_TARGET_MAX_UPSIDE_PCT:
            issue = _issue(
                "bearish_recommendation_high_target_price",
                "偏空或避免結論同時給出顯著高於現價的主要目標價。",
                details,
            )
            blocking.append(issue)
            checks.append(_check("recommendation_target_alignment", "blocked", issue["message"], details))
        elif recommendation_label == "持有" and abs(upside) >= HOLD_EXTREME_MOVE_PCT:
            issue = _issue(
                "hold_recommendation_extreme_target_move",
                "持有結論搭配極端目標價，需要人工確認風險報酬敘述。",
                details,
            )
            warnings.append(issue)
            checks.append(_check("recommendation_target_alignment", "warning", issue["message"], details))
        else:
            checks.append(_check("recommendation_target_alignment", "passed", "建議方向與主要目標價未見明顯矛盾。", details))
    elif recommendation or main_target:
        details = {"current_price": current_price, "target_price": main_target.get("price") if main_target else None}
        warnings.append(_issue("missing_price_alignment_inputs", "缺少現價或主要目標價，無法完成方向一致性檢查。", details))
        checks.append(_check("recommendation_target_alignment", "warning", "缺少方向一致性檢查輸入。", details))
    else:
        checks.append(_check("recommendation_target_alignment", "passed", "未記錄最終建議或主要目標價，略過方向一致性檢查。"))

    score = data_confidence_score(data_trust)
    if explicit_target_fields and score < EXPLICIT_TARGET_PRICE_MIN_SCORE:
        details = {
            "data_confidence_score": score,
            "min_data_confidence_score": EXPLICIT_TARGET_PRICE_MIN_SCORE,
            "detected_fields": explicit_target_fields,
            "data_trust_status": data_trust.get("status"),
        }
        issue = _issue(
            "explicit_target_price_low_data_confidence",
            "資料信心低於明確目標價門檻，但報告仍含明確目標價欄位。",
            details,
        )
        blocking.append(issue)
        checks.append(_check("data_confidence_target_guardrail", "blocked", issue["message"], details))
    elif data_trust.get("status") != "fresh":
        details = {"data_trust_status": data_trust.get("status"), "data_trust_label": trust_status_label(str(data_trust.get("status")))}
        warnings.append(_issue("non_fresh_data_trust", "資料可信度不是 fresh，內容可信度需保留限制。", details))
        checks.append(_check("data_confidence_target_guardrail", "warning", "資料可信度不是 fresh。", details))
    else:
        checks.append(_check("data_confidence_target_guardrail", "passed", "資料信心達到明確目標價門檻。", {"data_confidence_score": score}))

    if evidence_verdict == "rejected" and confidence_score is not None and confidence_score >= HIGH_CONFIDENCE_MIN_SCORE:
        details = {"evidence_verdict": evidence_verdict, "confidence_score": confidence_score}
        issue = _issue(
            "high_confidence_rejected_evidence",
            "證據抽查 rejected，但最終結論仍給出高信心。",
            details,
        )
        blocking.append(issue)
        checks.append(_check("confidence_evidence_alignment", "blocked", issue["message"], details))
    elif evidence_verdict not in {"approved", "not_recorded"}:
        details = {"evidence_verdict": evidence_verdict, "confidence_score": confidence_score}
        warnings.append(_issue("non_approved_evidence_gate", "證據抽查未完全通過，內容可信度需人工確認。", details))
        checks.append(_check("confidence_evidence_alignment", "warning", "證據抽查未完全通過。", details))
    else:
        checks.append(_check("confidence_evidence_alignment", "passed", "信心與證據抽查狀態未見明顯矛盾。", {"evidence_verdict": evidence_verdict}))

    if recommendation and not _has_evidence_claim(evidence_rows, "最終投資建議"):
        issue = _issue(
            "missing_final_recommendation_evidence",
            "最終投資建議缺少 evidence matrix 覆蓋。",
            {"required_claim": "最終投資建議"},
        )
        warnings.append(issue)
        checks.append(_check("evidence_matrix_coverage", "warning", issue["message"], issue["details"]))
    else:
        checks.append(_check("evidence_matrix_coverage", "passed", "最終投資建議已有 evidence matrix 覆蓋。"))

    if blocking:
        status = "blocked"
        summary = "報告關鍵結論與資料或證據存在阻斷矛盾。"
    elif warnings:
        status = "warning"
        summary = "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。"
    else:
        status = "passed"
        summary = "報告關鍵結論通過內容可信度檢查。"

    return {
        "schema_version": 1,
        "status": status,
        "summary": summary,
        "blocking_issues": blocking,
        "warnings": warnings,
        "checks": checks,
    }
