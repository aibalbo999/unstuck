"""Forward target price consistency and recommendation-return alignment checks."""

from __future__ import annotations

from typing import Optional


# -------------------------------------------------------------------
# 建議等級 vs 預期報酬率硬性約束矩陣
# -------------------------------------------------------------------
RECOMMENDATION_RETURN_GATES: dict[str, dict] = {
    "強烈放空": {
        "max_expected_return_pct": -15.0,
        "label": "強烈放空建議需要 12 個月預期跌幅 ≥15%",
    },
    "買入": {
        "min_expected_return_pct": 15.0,
        "label": "買入建議需要 12 個月預期報酬 ≥15%",
    },
    "買進": {
        "min_expected_return_pct": 15.0,
        "label": "買進建議需要 12 個月預期報酬 ≥15%",
    },
    "持有": {
        "min_expected_return_pct": 5.0,
        "max_expected_return_pct": 30.0,
        "label": "持有建議預期報酬應在 5-30% 範圍",
    },
    "避免": {
        "max_expected_return_pct": 10.0,
        "label": "避免建議不應有超過 10% 的 12 個月預期報酬",
    },
}

# 建議方向與目標價的方向一致性
RECOMMENDATION_DIRECTION: dict[str, str] = {
    "強烈放空": "down",
    "買入": "up",
    "買進": "up",
    "持有": "neutral",
    "避免": "down",
}

# 12 個月隱含年化報酬率異常上限（超過即觸發警示）
MAX_ANNUALIZED_RETURN_WARNING_PCT = 100.0

# 目標價逆向偏差容忍度（3m -> 6m -> 12m 允許的回撤比例）
TARGET_REVERSAL_TOLERANCE_PCT = 5.0


def _pct_change(new_price: float, base_price: float) -> Optional[float]:
    if base_price <= 0:
        return None
    return round((new_price / base_price - 1) * 100, 4)


def check_recommendation_return_alignment(
    recommendation: str,
    current_price: float,
    target_12m: Optional[float],
) -> list[str]:
    """驗證建議等級與 12 個月目標報酬率是否一致。

    Returns:
        list of issue strings (empty = no issues).
    """
    issues: list[str] = []
    if not recommendation or current_price is None or current_price <= 0:
        return issues
    if target_12m is None:
        return issues

    gate = RECOMMENDATION_RETURN_GATES.get(recommendation)
    if not gate:
        return issues

    expected_return = _pct_change(target_12m, current_price)
    if expected_return is None:
        return issues

    min_ret = gate.get("min_expected_return_pct")
    max_ret = gate.get("max_expected_return_pct")

    if min_ret is not None and expected_return < min_ret:
        issues.append(
            f"建議/報酬矛盾：建議為「{recommendation}」但 12 個月目標價 NT${target_12m:g} "
            f"相對現價 NT${current_price:g} 僅隱含 {expected_return:.1f}% 報酬，"
            f"低於「{recommendation}」所需最低 {min_ret:.0f}%。需要降低建議等級或提高目標價。"
        )

    if max_ret is not None and expected_return > max_ret:
        issues.append(
            f"建議/報酬矛盾：建議為「{recommendation}」但 12 個月目標價 NT${target_12m:g} "
            f"相對現價 NT${current_price:g} 隱含 {expected_return:.1f}% 報酬，"
            f"超過「{recommendation}」的合理上限 {max_ret:.0f}%。應升格為「買入」或說明折讓原因。"
        )

    if abs(expected_return) > MAX_ANNUALIZED_RETURN_WARNING_PCT:
        issues.append(
            f"目標報酬率異常：12 個月目標價隱含年化報酬 {expected_return:.1f}%，"
            "超過 100%；需要人工確認是否為估值假設錯誤或單位換算問題。"
        )

    return issues


def check_target_price_direction(
    recommendation: str,
    current_price: float,
    target_12m: Optional[float],
) -> list[str]:
    """驗證目標價方向與建議一致。"""
    issues: list[str] = []
    if not recommendation or current_price is None or current_price <= 0 or target_12m is None:
        return issues

    expected_direction = RECOMMENDATION_DIRECTION.get(recommendation)
    actual_return = _pct_change(target_12m, current_price)
    if actual_return is None or expected_direction is None:
        return issues

    if expected_direction == "up" and actual_return < 0:
        issues.append(
            f"方向矛盾：建議「{recommendation}」但 12 個月目標價 NT${target_12m:g} "
            f"低於現價 NT${current_price:g}（隱含跌幅 {abs(actual_return):.1f}%）。"
        )
    elif expected_direction == "down" and actual_return > 5:
        issues.append(
            f"方向矛盾：建議「{recommendation}」但 12 個月目標價 NT${target_12m:g} "
            f"高於現價 NT${current_price:g}（隱含漲幅 {actual_return:.1f}%）超過 5%。"
        )

    return issues


def check_target_price_sequence(
    target_3m: Optional[float],
    target_6m: Optional[float],
    target_12m: Optional[float],
    recommendation: str,
) -> list[str]:
    """驗證 3m/6m/12m 目標價時序合理性。

    買入/買進：預期目標價應大致遞增（允許小幅回撤）。
    避免/強烈放空：預期目標價應大致遞減（允許小幅回撤）。
    """
    issues: list[str] = []
    prices = [(label, price) for label, price in [("3個月", target_3m), ("6個月", target_6m), ("12個月", target_12m)] if price is not None]
    if len(prices) < 2:
        return issues

    direction = RECOMMENDATION_DIRECTION.get(recommendation, "neutral")
    if direction == "neutral":
        return issues

    for i in range(len(prices) - 1):
        label_a, price_a = prices[i]
        label_b, price_b = prices[i + 1]
        pct = _pct_change(price_b, price_a)
        if pct is None:
            continue
        if direction == "up" and pct < -TARGET_REVERSAL_TOLERANCE_PCT:
            issues.append(
                f"目標價時序異常：買入建議下 {label_b} 目標 NT${price_b:g} "
                f"比 {label_a} 目標 NT${price_a:g} 低 {abs(pct):.1f}%，"
                "超過允許回撤幅度，需說明近期壓力情境。"
            )
        elif direction == "down" and pct > TARGET_REVERSAL_TOLERANCE_PCT:
            issues.append(
                f"目標價時序異常：避免建議下 {label_b} 目標 NT${price_b:g} "
                f"比 {label_a} 目標 NT${price_a:g} 高 {abs(pct):.1f}%，"
                "超過允許幅度，與避免建議方向矛盾。"
            )

    return issues


def run_forward_consistency_checks(
    recommendation: str,
    current_price: Optional[float],
    target_3m: Optional[float],
    target_6m: Optional[float],
    target_12m: Optional[float],
) -> dict[str, list[str]]:
    """執行所有前向一致性檢查，回傳分類結果。"""
    if not recommendation or current_price is None or current_price <= 0:
        return {"critical": [], "warnings": []}

    critical: list[str] = []
    warnings: list[str] = []

    # 建議/報酬矛盾為 critical
    critical.extend(check_recommendation_return_alignment(recommendation, current_price, target_12m))
    critical.extend(check_target_price_direction(recommendation, current_price, target_12m))

    # 時序問題為 warning
    warnings.extend(check_target_price_sequence(target_3m, target_6m, target_12m, recommendation))

    return {"critical": critical, "warnings": warnings}
