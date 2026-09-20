"""Recommendation and target-price alignment checks for content credibility."""
from __future__ import annotations
import re
from typing import Any
from mapping_fields import safe_mapping_dict, safe_text
from recommendation_labels import CANONICAL_RECOMMENDATIONS
from trade_execution_contract import contains_trade_order, observation_reason_is_explicit, short_observation_is_explicit
from trade_price_inputs import execution_value_missing
from .content_credibility_inputs import upside_pct
BUY_TARGET_MIN_UPSIDE_PCT = 0.0
BEARISH_TARGET_MAX_UPSIDE_PCT = 10.0
HOLD_EXTREME_MOVE_PCT = 30.0


def _explicit_no_position(short_setup: Any) -> bool:
    """A price-free, affirmative no-position contract; silence is insufficient."""
    setup = safe_mapping_dict(short_setup) or {}
    entry = safe_text(setup.get("entry_trigger"))
    stop = safe_text(setup.get("cover_stop"))
    target = safe_text(setup.get("downside_target"))
    no_position = r"(?:^|[，。；、\n])\s*(?:目前|暫時|現在)?\s*不(?:開倉|建倉|交易|建立(?:新|空方)?部位)(?=[，。；、\n]|$)"
    return (
        short_observation_is_explicit(setup)
        and bool(re.search(no_position, entry))
        and bool(re.search(no_position, stop))
        and "不適用" in stop
        and execution_value_missing(setup.get("downside_target"))
        and not re.search(r"\d", f"{entry} {target} {stop}")
        and not contains_trade_order(f"{entry} {target} {stop}")
        and not re.search(r"持有|持倉|既有|現有|已建立|回補|加碼|減碼", f"{entry} {target} {stop}")
        and observation_reason_is_explicit(setup.get("squeeze_risk"))
        and observation_reason_is_explicit(setup.get("thesis_invalidation"))
    )


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
    pipeline_id: str = "",
    short_setup: dict[str, Any] | None = None,
) -> dict:
    """Evaluate whether the final recommendation direction matches target price."""
    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if recommendation_present and recommendation_label not in CANONICAL_RECOMMENDATIONS:
        details = {
            "recommendation": recommendation_label,
            "current_price": current_price,
            "target_price": main_target.get("price") if main_target else None,
            "target_source": main_target.get("source") if main_target else None,
            "allowed_recommendations": list(CANONICAL_RECOMMENDATIONS),
        }
        issue = _issue(
            "unrecognized_recommendation_label",
            "最終建議不是可辨識的投資方向，無法完成方向一致性檢查。",
            details,
        )
        warnings.append(issue)
        checks.append(_check("recommendation_target_alignment", "warning", issue["message"], details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

    if (pipeline_id == "v3" and recommendation_present and recommendation_label == "避免"
            and main_target is None and _explicit_no_position(short_setup)):
        details = {"pipeline_id": "v3", "recommendation": "避免", "current_price": current_price,
                   "target_price": None, "contract_scope": "v3_explicit_no_position",
                   "contract_verified": True, "execution_status": "no_position",
                   "analysis_completeness": "not_evaluated"}
        checks.append(_check("recommendation_target_alignment", "not_applicable",
            "已確認目前不建立空方部位，目標價方向檢查不適用；不代表分析完整性或證據品質已通過。", details))
        return {"blocking_issues": blocking, "warnings": warnings, "checks": checks}

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
        elif recommendation_label == "放空" and upside >= BEARISH_TARGET_MAX_UPSIDE_PCT:
            issue = _issue(
                "bearish_recommendation_high_target_price",
                "放空結論同時給出顯著高於現價的主要目標價。",
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
