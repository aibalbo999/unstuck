"""Pure sizing calculations using caller-supplied, source-bound financial inputs.

The caller owns the trust boundary: ``supplied_inputs`` must come from an
explicit request/scenario, never from an agent's output. These functions do not
create missing capital, risk budgets, holdings or trade orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal, ROUND_DOWN

from mapping_fields import safe_mapping_dict
from recommendation_labels import normalize_recommendation_label
from trade_price_inputs import parse_position_percentage, parse_price_range


SIZING_METHOD = "explicit_loss_budget_v1"
SIZING_FORMULA = "risk_limit_percent = floor_6dp(min(risk_budget_amount / risk_per_share * entry_reference / capital_amount * 100, 100)); risk_per_share = worst_entry_stop_distance + round_trip_cost; position_percent = existing_position_percent for hold, otherwise risk_limit_percent; reduce requires existing_position_percent > risk_limit_percent"
_INPUT_FIELDS = (
    "capital_amount", "risk_budget_amount", "currency", "scenario_type",
    "position_state", "existing_position_percent",
)


def _finite(value, *, zero=False) -> bool:
    try:
        return (
            type(value) in {int, float} and math.isfinite(value)
            and (value >= 0 if zero else value > 0)
        )
    except OverflowError:
        return False


def build_position_sizing_context(
    supplied_inputs=None, *, source_ref=None, quote_currency=None,
) -> dict:
    """Validate explicit inputs; source identity is separate from model fields."""
    raw = safe_mapping_dict(supplied_inputs) or {}
    inputs = {key: raw.get(key) for key in _INPUT_FIELDS}
    issues = []
    if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 256:
        issues.append("缺少明確輸入的來源身分")
    for key in ("capital_amount", "risk_budget_amount"):
        if not _finite(inputs[key]):
            issues.append(f"{key} 必須由來源提供有限正數")
    if _finite(inputs["capital_amount"]) and _finite(inputs["risk_budget_amount"]):
        if inputs["risk_budget_amount"] > inputs["capital_amount"]:
            issues.append("風險金額不得超過資金基準")
    currency = inputs["currency"]
    if (
        not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)
        or currency != quote_currency
    ):
        issues.append("資金與報價必須有相同且明確的幣別")
    if inputs["scenario_type"] not in ("research", "actual"):
        issues.append("必須明示研究假設或實際輸入情境")
    state, existing = inputs["position_state"], inputs["existing_position_percent"]
    if state not in ("no_position", "holding") or not _finite(existing, zero=True) or existing > 100:
        issues.append("既有部位狀態及占資金比例必須明確提供")
    elif (state == "no_position" and existing != 0) or (state == "holding" and existing <= 0):
        issues.append("既有部位狀態與比例不一致")
    if issues:
        return {
            "status": "unavailable", "reason": "；".join(issues),
            "source_ref": source_ref if isinstance(source_ref, str) else None,
            "context_sha256": None,
        }
    payload = {"inputs": inputs, "source_ref": source_ref.strip(), "quote_currency": quote_currency}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return {"status": "available", **payload, "context_sha256": digest}


def _verified_context(context) -> dict | None:
    context = safe_mapping_dict(context) or {}
    rebuilt = build_position_sizing_context(
        context.get("inputs"), source_ref=context.get("source_ref"), quote_currency=context.get("quote_currency"),
    )
    if context.get("status") != "available" or rebuilt.get("status") != "available":
        return None
    return rebuilt if context.get("context_sha256") == rebuilt["context_sha256"] else None


def _unassessed(reason: str) -> dict:
    return {
        "status": "unassessed", "reason": reason,
        "method": None, "formula": None, "source_ref": None, "context_sha256": None,
        "capital_amount": None, "risk_budget_amount": None, "currency": None,
        "scenario_type": "unassessed", "position_state": "unknown", "existing_position_percent": None,
        "risk_per_share": None, "entry_reference": None, "round_trip_cost": None,
        "risk_limit_percent": None, "position_percent": None,
        "trade_direction": None, "horizon_trading_days": None,
    }


def _cost(value) -> float | None:
    if type(value) in {int, float}:
        return float(value) if _finite(value, zero=True) else None
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(?:NT\$|TWD|\$)?\s*(\d+(?:\.\d+)?)\s*(?:元|TWD)?\s*", value)
    result = float(match[1]) if match else None
    return result if result is not None and math.isfinite(result) else None


def calculate_position_sizing(position_plan, sizing_context=None, *, recommendation=None) -> dict:
    """Return a receipt only; never rewrite an unverified model plan or prose.

    Percentages describe resulting total exposure against the named capital
    basis, including for 減碼. Short sizing is a risk limit, not proof that shares
    can be borrowed or that a trade can be executed.
    """
    context = _verified_context(sizing_context)
    if context is None:
        return _unassessed("資金基準、風險預算或持倉情境未提供可驗證來源；比例未評估，不能推定使用者實際持倉。")
    plan = safe_mapping_dict(position_plan) or {}
    inputs = context["inputs"]
    action = plan.get("action")
    if action not in ("進場", "續抱", "減碼"):
        return _unassessed("目前為等待研究計畫，不建立新的部位；不代表使用者實際持倉為零。")
    if (action == "進場" and inputs["position_state"] != "no_position") or (
        action in {"續抱", "減碼"} and inputs["position_state"] != "holding"
    ):
        return _unassessed("動作與明確提供的持倉情境不符，不得推定既有部位。")
    entry, stop = parse_price_range(plan.get("entry_zone")), parse_price_range(plan.get("stop_loss"))
    cost = _cost(plan.get("transaction_cost"))
    horizon = plan.get("horizon_trading_days")
    if not entry or not stop or cost is None or type(horizon) is not int or not 1 <= horizon <= 252:
        return _unassessed("缺少可驗證的進場、停損、每股來回成本或共同交易期間，sizing 無法計算。")
    label = recommendation.get("建議", recommendation.get("recommendation")) if isinstance(recommendation, dict) else recommendation
    short = normalize_recommendation_label(label) == "放空"
    if (short and stop[0] <= entry[1]) or (not short and stop[1] >= entry[0]):
        return _unassessed("停損必須位於完整進場區間的正確方向，sizing 無法計算。")
    entry_reference = entry[0] if short else entry[1]
    risk = (stop[1] - entry[0] if short else entry[1] - stop[0]) + cost
    if not math.isfinite(risk) or risk <= 0:
        return _unassessed("每股風險不是可驗證有限正數。")
    raw = min(
        Decimal(str(inputs["risk_budget_amount"])) / Decimal(str(risk))
        * Decimal(str(entry_reference)) / Decimal(str(inputs["capital_amount"])) * 100,
        Decimal(100),
    )
    percentage = float(raw.quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
    existing = inputs["existing_position_percent"]
    risk_limit = percentage
    if percentage <= 0 or (action == "續抱" and existing > percentage) or (action == "減碼" and existing <= percentage):
        return _unassessed("既有部位與風險預算不支持此續抱／減碼或正數部位，需重新評估動作。")
    if action == "續抱":
        percentage = existing
    return {
        "status": "calculated", "reason": "依明確輸入與最不利價格計算總部位上限；不代表交易可執行性已驗證。",
        "method": SIZING_METHOD, "formula": SIZING_FORMULA,
        "source_ref": context["source_ref"], "context_sha256": context["context_sha256"],
        **inputs, "risk_per_share": risk, "entry_reference": entry_reference,
        "round_trip_cost": cost, "risk_limit_percent": risk_limit, "position_percent": percentage,
        "trade_direction": "Short" if short else "Long", "horizon_trading_days": horizon,
    }


def position_sizing_contract_issues(position_plan, sizing_context=None, *, recommendation=None) -> list[str]:
    """Reject self-authored inputs and recompute receipts from trusted context."""
    plan = safe_mapping_dict(position_plan) or {}
    receipt = safe_mapping_dict(plan.get("sizing_evidence"))
    if plan.get("action") == "等待":
        if receipt and receipt.get("status") != "unassessed":
            return ["等待計畫的 sizing 不得宣稱已計算可執行部位。"]
        if receipt and any(receipt.get(key) is not None for key in (
            "capital_amount", "risk_budget_amount", "existing_position_percent",
            "risk_per_share", "position_percent", "risk_limit_percent", "entry_reference", "round_trip_cost",
            "method", "formula", "source_ref", "context_sha256",
        )):
            return ["未評估的 sizing 不得附加模型自行填入的資金、部位數字或來源收據。"]
        if receipt and (not isinstance(receipt.get("reason"), str) or not receipt["reason"].strip()):
            return ["未評估的 sizing 必須說明限制，不能推定使用者持倉。"]
        if plan.get("planning_context") in ("research", "actual") and _verified_context(sizing_context) is None:
            return ["position sizing 無可信輸入，不得宣称已有研究資金或實際持倉情境。"]
        # Old read-only snapshots may lack these additive fields. Waiting is
        # already constrained to a no-new-position plan by the execution gate.
        return []
    expected = calculate_position_sizing(plan, sizing_context, recommendation=recommendation)
    if expected["status"] != "calculated":
        return [f"position sizing 未評估：{expected['reason']}"]
    issues = []
    if plan.get("planning_context") != expected["scenario_type"]:
        issues.append("position sizing 必須明示與可信輸入一致的 research / actual 情境。")
    parsed = parse_position_percentage(plan.get("position_size"))
    if parsed is None or parsed[0] != parsed[1] or not math.isclose(parsed[0], expected["position_percent"], rel_tol=0, abs_tol=0.0000001):
        issues.append("position_size 與來源綁定的 deterministic sizing 計算不一致。")
    fields = set(expected) - {"reason"}
    if not receipt or any(type(receipt.get(key)) is bool or receipt.get(key) != expected[key] for key in fields):
        issues.append("position sizing_evidence 缺少或不符合資金、風險、持倉、來源及公式重算收據。")
    if issues:
        # Expose one bounded runtime calculation to the existing repair loop.
        # This is evidence for a new full response, never an accepted rewrite
        # of the model's unsupported position or its accompanying prose.
        evidence_json = json.dumps(expected, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
        issues[-1] += (
            " 系統依可信輸入重算的收據如下；這不是已接受的輸出，須同步修正 position_plan、比例及正文，並重新通過完整檢查："
            + evidence_json
        )
    return issues
