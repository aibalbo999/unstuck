"""Deterministic execution checks shared by mode contracts and report projection."""

from __future__ import annotations

import math
import re

from data_trust_values import has_value
from mapping_fields import safe_text
from trade_price_inputs import execution_value_missing, parse_position_percentage, parse_price_range, parse_risk_reward


def observation_reason_is_explicit(value) -> bool:
    """An honest missing-data explanation may still contain a concrete recheck."""
    text = safe_text(value)
    return has_value(text) and bool(re.search(
        r"法說|財報|財測|營收|公告|量能|成交量|突破|跌破|回測|均線|指引|外資|法人|籌碼|借券|融券|毛利|現金流|應收|軋空|重新(?:檢查|評估)|earnings|recheck|squeeze",
        text, re.I,
    ))


def contains_trade_order(value) -> bool:
    """Conservatively distinguish a deferred order from observation-only text."""
    text = safe_text(value)
    verbs = r"(?:建立空方部位|建立空單|買入|賣出|做多|做空|放空|開倉|建倉|進場|下單)"
    text = re.sub(r"(?:暫不|尚不|不可|不|勿|禁止|不得)\s*(?:立即|馬上|考慮)?\s*" + verbs, "", text)
    text = re.sub(r"\b(?:no|not|do not|don't)\s+(?:buy|sell|short|trade)\b", "", text, flags=re.I)
    return bool(re.search(verbs + r"|\b(?:buy|sell|short|open\s+(?:a\s+)?position)\b", text, re.I))


def neutral_observation_is_explicit(setup: dict) -> bool:
    entry = safe_text(setup.get("entry_zone"))
    catalyst = safe_text(setup.get("core_catalyst"))
    return (
        setup.get("trade_direction") == "Neutral"
        and bool(re.search(r"等待|暫不|不進場|不交易|觀望|wait|no.trade", f"{entry} {catalyst}", re.I))
        and observation_reason_is_explicit(catalyst)
        and not contains_trade_order(f"{entry} {catalyst}")
        and setup.get("risk_level") in {"High", "Medium", "Low"}
    )


def short_observation_is_explicit(setup: dict) -> bool:
    text = safe_text(setup.get("entry_trigger"))
    # Waiting for a later assessment is not an order to open a short on trigger.
    if not re.search(r"等待|觀望|暫不|不放空|不開倉|不建倉|不建立|wait|no.trade", text, re.I):
        return False
    return not contains_trade_order(text)


def evaluate_trade_execution(
    *, direction, entry_zone, target_price, stop_loss,
    position_size=None, risk_reward=None, transaction_cost=None, require_target=True,
) -> dict:
    """Return errors and evidence; cost is round-trip price units per share, not %.

    The least favorable entry/target/stop endpoints determine the ratio. An
    unavailable target or trading cost remains unknown and never becomes zero.
    """
    entry = parse_price_range(entry_zone)
    target = parse_price_range(target_price)
    stop = parse_price_range(stop_loss)
    issues = []
    details = {
        "trade_direction": direction,
        "entry_range": list(entry) if entry else None,
        "target_range": list(target) if target else None,
        "stop_range": list(stop) if stop else None,
        "worst_case_risk_reward": None,
        "transaction_cost": None,
        "net_risk_reward": None,
        "risk_reward_status": "unverifiable",
    }

    def add(code, message):
        issues.append({"id": code, "message": message})

    if direction not in {"Long", "Short"}:
        add("invalid_trade_direction", "交易方向不足，無法驗證可執行交易。")
    for field, parsed, required in (("entry_zone", entry, True), ("target_price", target, require_target), ("stop_loss", stop, True)):
        if parsed is None and (required or not execution_value_missing(target_price)):
            add(f"invalid_{field}", f"{field} 必須是可解析的正數價格或單一明確價格區間。")

    if position_size is not None:
        position = parse_position_percentage(position_size)
        details["position_percentage"] = list(position) if position else None
        if position is None or position[0] <= 0:
            add("invalid_position_size", "position_size 必須是大於 0 且不超過 100% 的部位百分比。")

    if entry and stop and direction in {"Long", "Short"}:
        invalid_stop = stop[1] >= entry[0] if direction == "Long" else stop[0] <= entry[1]
        if invalid_stop:
            add(f"{direction.lower()}_stop_not_outside_entry", "stop_loss / cover_stop 未位於完整進場區間的正確停損方向。")
    if entry and target and direction in {"Long", "Short"}:
        invalid_target = target[0] <= entry[1] if direction == "Long" else target[1] >= entry[0]
        if invalid_target:
            add(f"{direction.lower()}_target_not_outside_entry", "target_price / downside_target 未位於完整進場區間的獲利方向。")

    if not issues and entry and target and stop:
        reward = target[0] - entry[1] if direction == "Long" else entry[0] - target[1]
        risk = entry[1] - stop[0] if direction == "Long" else stop[1] - entry[0]
        ratio = reward / risk
        details["worst_case_risk_reward"] = ratio
        details["risk_reward_status"] = "gross_verified_cost_unknown"
        if isinstance(transaction_cost, (int, float, bool)) or not execution_value_missing(transaction_cost):
            try:
                cost = float(transaction_cost)
            except (ValueError, TypeError):
                cost_range = parse_price_range(transaction_cost)
                cost = cost_range[0] if cost_range and cost_range[0] == cost_range[1] else math.nan
                if re.fullmatch(r"\s*(?:NT\$|TWD|\$)?\s*0(?:\.0+)?\s*(?:元|TWD)?\s*", safe_text(transaction_cost), re.I):
                    cost = 0.0
            if not math.isfinite(cost) or cost < 0 or isinstance(transaction_cost, bool):
                add("invalid_transaction_cost", "transaction_cost 必須是明確的非負每股來回交易成本，不能把百分比當金額。")
            else:
                details["transaction_cost"] = cost
                details["net_risk_reward"] = (reward - cost) / (risk + cost)
                details["risk_reward_status"] = "net_verified"
                if reward <= cost:
                    add("transaction_cost_exceeds_reward", "transaction_cost 已抵銷最差進場情境的預期價差。")

    claimed = parse_risk_reward(risk_reward)
    details["claimed_risk_reward"] = claimed
    if not execution_value_missing(risk_reward) and re.search(r"\d\s*[:/]", safe_text(risk_reward)) and claimed is None:
        add("invalid_risk_reward", "risk_reward 明確比率必須是正數且只有一個可辨識比率。")
    calculated = details["net_risk_reward"] if details["transaction_cost"] is not None else details["worst_case_risk_reward"]
    if claimed is not None and calculated is not None and not math.isclose(claimed, calculated, rel_tol=0.05, abs_tol=0.05):
        add("risk_reward_mismatch", "risk_reward 與最差進場價格、目標、停損及已知成本驗算不一致。")
    return {"issues": issues, "details": details}


__all__ = ["evaluate_trade_execution", "neutral_observation_is_explicit", "observation_reason_is_explicit", "short_observation_is_explicit"]
