"""Mode-specific final-report contract checks."""

from __future__ import annotations

import math
import re
import unicodedata

from data_trust_values import has_value
from mapping_fields import safe_text
from recommendation_labels import normalize_recommendation_label
from structured_output_normalizer import structured_output_to_report_text
from validators import strip_generated_audit_sections
from trade_execution_contract import contains_trade_order, evaluate_trade_execution, neutral_observation_is_explicit, observation_reason_is_explicit, short_observation_is_explicit
from trade_price_inputs import parse_position_percentage, price_contract_text


REQUIRED_TRADE_SETUP_FIELDS = {
    "trade_direction",
    "entry_zone",
    "target_price",
    "stop_loss",
    "support_level",
    "resistance_level",
    "core_catalyst",
    "risk_level",
}
REQUIRED_POSITION_PLAN_FIELDS = {
    "action",
    "entry_zone",
    "position_size",
    "stop_loss",
    "risk_reward",
    "invalidation_condition",
}
REQUIRED_SHORT_SETUP_FIELDS = {
    "entry_trigger",
    "downside_target",
    "cover_stop",
    "squeeze_risk",
    "thesis_invalidation",
}
_PRICE_RANGE_RE = re.compile(r"\d[\d,.]*\s*(?:元|NT\$|TWD)?\s*(?:-|–|—|－|−|~|～|至|到)\s*(?:NT\$|TWD)?\s*\d")
_HORIZON_RANGE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:-|–|—|－|−|~|～|至|到)\s*"
    r"\d+(?:\.\d+)?\s*(?:個)?(?:交易日|日|天|週|周|月|季|年|trading\s+days?|days?|weeks?|months?|quarters?|years?)",
    re.IGNORECASE,
)
_HORIZON_VALUE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:個)?(?:交易日|日|天|週|周|月|季|年|trading\s+days?|days?|weeks?|months?|quarters?|years?)",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"[+\-]?\d+(?:\.\d+)?\s*%")
_NEGATIVE_PRICE_RE = re.compile(r"(?<!\d)(?:NT\$|TWD|\$)?\s*-\s*\d", re.IGNORECASE)
_TARGET_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![A-Za-z0-9_.])"
)
_INVALID_PRICE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[+-]?(?:inf(?:inity)?|nan)|\d+(?:\.\d+)?[eE][+-]?\d+)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_INSUFFICIENT_VALUE_MARKERS = ("資料不足", "待補", "無法驗證")


def _execution_value_is_missing(value) -> bool:
    text = safe_text(value).strip()
    return not has_value(text) or any(marker in text for marker in _INSUFFICIENT_VALUE_MARKERS)


def _recommendation_block_at_tail(text: str) -> bool:
    return bool(re.search(r"\[投資建議\].*?\[/投資建議\]\s*$", text or "", re.DOTALL))


def _target_price_contract_text(value) -> str:
    text = unicodedata.normalize("NFKC", safe_text(value))
    text = _HORIZON_RANGE_RE.sub("", text)
    return price_contract_text(_PERCENT_RE.sub("", _HORIZON_VALUE_RE.sub("", text)))


def _target_price_contract_numbers(text: str) -> tuple[list[float], bool]:
    if _NEGATIVE_PRICE_RE.search(text):
        return [], True
    numbers = []
    has_invalid_number = bool(_INVALID_PRICE_TOKEN_RE.search(text))
    for match in _TARGET_NUMBER_RE.finditer(text):
        number = float(match.group(0).replace(",", ""))
        if math.isfinite(number):
            numbers.append(number)
        else:
            has_invalid_number = True
    return numbers, has_invalid_number


def v3_recommendation_contract_issues(
    analyses: dict,
    structured_outputs: dict,
    recommendation_agent: int | None,
    completed_agents: set[int],
) -> list[str]:
    if recommendation_agent is None:
        return []

    final_text = strip_generated_audit_sections(str(analyses.get(recommendation_agent, "")))
    structured = structured_outputs.get(recommendation_agent)
    if isinstance(structured, dict):
        final_text = strip_generated_audit_sections(
            structured_output_to_report_text(recommendation_agent, structured, final_text)
        )

    issues = []
    if "做空觸發條件（Catalyst for crash）" not in final_text:
        issues.append("缺少做空觸發條件（Catalyst for crash）章節。")
    if "防軋空停損點（Stop-loss level）" not in final_text:
        issues.append("缺少防軋空停損點（Stop-loss level）章節。")
    if recommendation_agent in completed_agents and not _recommendation_block_at_tail(final_text):
        issues.append("最終 [投資建議] 區塊未位於 Agent 19 輸出尾端。")
    return issues


def v2_position_plan_contract_issues(position_plan: dict, *, target_price=None, recommendation=None) -> list[str]:
    issues = []
    waiting = position_plan.get("action") == "等待"
    required = {"action", "position_size", "invalidation_condition"} if waiting else REQUIRED_POSITION_PLAN_FIELDS
    missing = sorted(key for key in required if (
        not observation_reason_is_explicit(position_plan.get(key))
        if waiting and key == "invalidation_condition"
        else _execution_value_is_missing(position_plan.get(key))
    ))
    if missing:
        issues.append(f"缺少或資料不足的實戰部位欄位：{', '.join(missing)}")
    if position_plan.get("action") not in {"進場", "續抱", "減碼", "等待"}:
        issues.append(f"position action 不在允許值內：{position_plan.get('action') or '空白'}")
    if waiting:
        if contains_trade_order(position_plan.get("entry_zone")):
            issues.append("等待且零部位的計畫不得同時包含買賣或進場指令。")
        if parse_position_percentage(position_plan.get("position_size")) != (0.0, 0.0):
            issues.append("等待時 position_size 必須明確為 0%，不得將未知部位當成零。")
        return issues
    label = recommendation.get("建議", recommendation.get("recommendation")) if isinstance(recommendation, dict) else recommendation
    direction = "Short" if normalize_recommendation_label(label) == "放空" else "Long"
    execution = evaluate_trade_execution(
        direction=direction if position_plan.get("action") in {"進場", "續抱", "減碼"} else None,
        entry_zone=position_plan.get("entry_zone"),
        target_price=position_plan.get("target_price") or target_price,
        stop_loss=position_plan.get("stop_loss"), position_size=position_plan.get("position_size"),
        risk_reward=position_plan.get("risk_reward"), transaction_cost=position_plan.get("transaction_cost"),
        require_target=False,
    )
    issues.extend(issue["message"] for issue in execution["issues"])
    return issues


def v3_short_setup_contract_issues(short_setup: dict, *, recommendation=None) -> list[str]:
    label = recommendation.get("建議", recommendation.get("recommendation")) if isinstance(recommendation, dict) else recommendation
    observation = label in {"避免", "持有", "買入"}
    required = {"entry_trigger", "squeeze_risk", "thesis_invalidation"} if observation else REQUIRED_SHORT_SETUP_FIELDS
    missing = sorted(key for key in required if (
        not observation_reason_is_explicit(short_setup.get(key))
        if observation and key in {"squeeze_risk", "thesis_invalidation"}
        else _execution_value_is_missing(short_setup.get(key))
    ))
    issues = [f"缺少或資料不足的逆勢交易欄位：{', '.join(missing)}"] if missing else []
    if observation:
        if not short_observation_is_explicit(short_setup):
            issues.append("非放空建議必須明確等待或不開倉，entry_trigger 不得混入建立空單的執行指令。")
        return issues
    execution = evaluate_trade_execution(
        direction="Short", entry_zone=short_setup.get("entry_trigger"),
        target_price=short_setup.get("downside_target"), stop_loss=short_setup.get("cover_stop"),
        transaction_cost=short_setup.get("transaction_cost"),
    )
    return issues + [issue["message"] for issue in execution["issues"]]


def v4_trade_setup_contract_issues(trade_setup: dict) -> list[str]:
    issues = []
    if neutral_observation_is_explicit(trade_setup):
        return issues
    if trade_setup.get("trade_direction") == "Neutral" and contains_trade_order(
        f"{safe_text(trade_setup.get('entry_zone'))} {safe_text(trade_setup.get('core_catalyst'))}"
    ):
        issues.append("Neutral 不交易計畫不得同時包含買賣或進場指令。")
    missing = sorted(
        key for key in REQUIRED_TRADE_SETUP_FIELDS if _execution_value_is_missing(trade_setup.get(key))
    )
    if missing:
        issues.append(f"缺少或資料不足的極短線交易欄位：{', '.join(missing)}")
    if trade_setup.get("trade_direction") not in {"Long", "Short", "Neutral"}:
        issues.append(f"trade_direction 不在允許值內：{trade_setup.get('trade_direction') or '空白'}")
    if trade_setup.get("risk_level") not in {"High", "Medium", "Low"}:
        issues.append(f"risk_level 不在允許值內：{trade_setup.get('risk_level') or '空白'}")
    raw_target_text = unicodedata.normalize("NFKC", safe_text(trade_setup.get("target_price", "")))
    target_has_horizon = bool(_HORIZON_RANGE_RE.search(raw_target_text) or _HORIZON_VALUE_RE.search(raw_target_text))
    target_text = _target_price_contract_text(raw_target_text)
    target_numbers, target_has_invalid_number = _target_price_contract_numbers(target_text)
    if target_has_horizon:
        issues.append("target_price 不得包含交易期間，請只保留目標價格或明確價格區間。")
    if target_has_invalid_number:
        issues.append("target_price 含無效或非有限價格，必須重新產生可驗證目標價。")
    if not target_numbers:
        issues.append("target_price 必須包含至少一個可解析價格。")
    elif any(price <= 0 for price in target_numbers):
        issues.append("target_price 的所有價格必須大於零。")
    elif len(target_numbers) > 2 or (
        len(target_numbers) == 2 and not _PRICE_RANGE_RE.search(target_text)
    ):
        issues.append("target_price 含多個價位，必須改為單一目標或一個明確價格區間。")
    if trade_setup.get("trade_direction") in {"Long", "Short"}:
        execution = evaluate_trade_execution(
            direction=trade_setup.get("trade_direction"), entry_zone=trade_setup.get("entry_zone"),
            target_price=trade_setup.get("target_price"), stop_loss=trade_setup.get("stop_loss"),
            risk_reward=trade_setup.get("risk_reward"), transaction_cost=trade_setup.get("transaction_cost"),
        )
        issues.extend(issue["message"] for issue in execution["issues"])
    return issues


def mode_execution_contract_issues(
    parsed: dict,
    *,
    position_plan_agent: int | None,
    short_setup_agent: int | None,
    trade_setup_agent: int | None,
) -> list[tuple[int, str]]:
    """Return mode-specific repair issues with the responsible final agent."""
    checks = (
        (position_plan_agent, v2_position_plan_contract_issues, "position_plan"),
        (short_setup_agent, v3_short_setup_contract_issues, "short_setup"),
        (trade_setup_agent, v4_trade_setup_contract_issues, "trade_setup"),
    )
    issues = []
    for agent_num, checker, field in checks:
        if agent_num is None:
            continue
        kwargs = {"recommendation": parsed.get("recommendation")} if field in {"position_plan", "short_setup"} else {}
        issues.extend((agent_num, issue) for issue in checker(parsed.get(field, {}) or {}, **kwargs))
    return issues
