"""Recommendation and target-price alignment checks for content credibility."""

from __future__ import annotations

from typing import Any

from .content_credibility_inputs import upside_pct


BUY_TARGET_MIN_UPSIDE_PCT = 0.0
BEARISH_TARGET_MAX_UPSIDE_PCT = 10.0
HOLD_EXTREME_MOVE_PCT = 30.0


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


def evaluate_recommendation_target_alignment(
    *,
    recommendation_present: bool,
    recommendation_label: str,
    current_price: float | None,
    main_target: dict[str, Any] | None,
) -> dict:
    """Evaluate whether the final recommendation direction matches target price."""
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if current_price and main_target:
        target_price = float(main_target["price"])
        upside = upside_pct(target_price, current_price)
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
    elif recommendation_present or main_target:
        details = {"current_price": current_price, "target_price": main_target.get("price") if main_target else None}
        warnings.append(_issue("missing_price_alignment_inputs", "缺少現價或主要目標價，無法完成方向一致性檢查。", details))
        checks.append(_check("recommendation_target_alignment", "warning", "缺少方向一致性檢查輸入。", details))
    else:
        checks.append(_check("recommendation_target_alignment", "passed", "未記錄最終建議或主要目標價，略過方向一致性檢查。"))

    return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}
