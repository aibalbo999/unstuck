"""Source-bound research execution metadata, separate from market evidence."""

import re

from mapping_fields import safe_mapping_dict


_ZERO_PERCENT = re.compile(r"0(?:\.0+)?\s*%")
_WAITING_ROW = re.compile(r"(?:[-+]\s*)?(?:操作動作|部位動作)\s*[:：]\s*(\S+)\s*$")
_SIZE_ROW = re.compile(r"(?:[-+]\s*)?部位大小\s*[:：]\s*0(?:\.0+)?\s*%\s*$")
_HOLDING_SCOPE = re.compile(
    r"(?:使用者|用戶|投資人)\s*(?:(?:的|目前|當前|現有|實際)\s*)*(?:持倉|持股)"
    r"|(?:目前|當前|現有|實際)\s*(?:持倉|持股)"
)
_UNKNOWN_HOLDING_PREFIX = re.compile(
    r"(?:不代表|並非|不是|不能代表|無法代表|不等於|未(?:能)?(?:取得|確認|核實)|"
    r"尚未(?:取得|確認|核實)|缺少|缺乏|未知|無法確認|待(?:取得|確認|核實))\s*$"
)
_CALCULATION_UNKNOWN_FIELDS = (
    "capital_amount", "risk_budget_amount", "existing_position_percent", "position_percent",
    "risk_limit_percent", "risk_per_share", "entry_reference", "round_trip_cost",
    "method", "formula", "source_ref", "context_sha256", "trade_direction", "horizon_trading_days",
    "currency",
)


def _plain(text):
    return re.sub(r"[*_`]", "", str(text or "")).strip()


def _conflicting_policy_text(text):
    """Reject asserted account scope/orders; a disclaimer is not an assertion.

    Inspect each clause separately so a preceding disclaimer or conditional does
    not excuse a later assertion. Headings are included in this same check.
    """
    from position_sizing_narrative import waiting_plan_has_immediate_order

    text = _plain(text)
    if waiting_plan_has_immediate_order(text):
        return True
    for clause in re.split(r"[。！？\n；;，,]", text):
        for match in _HOLDING_SCOPE.finditer(clause):
            prefix = clause[:match.start()].strip().lstrip("#>-+ ")
            if (_UNKNOWN_HOLDING_PREFIX.search(prefix)
                    or re.fullmatch(r"(?:若|如果|假設).*", prefix)):
                continue
            return True
    return False


def verified_position_policy_claim(claim, snapshot, rendered_text):
    """Recognize only a checked wait/zero row, not arbitrary model allocations.

    The saved runtime receipt must agree with both report projections and a fresh
    local contract check. This validates a research no-new-position policy; it
    never verifies account holdings or market facts, and never exempts nonzero
    allocations from the ordinary evidence gate.
    """
    if claim.get("label") != "部位大小" or claim.get("unit") != "%" or claim.get("reported_value") != 0:
        return None
    if not _SIZE_ROW.fullmatch(_plain(claim.get("raw_text"))):
        return None
    if _conflicting_policy_text(rendered_text):
        return None
    actions = [match[1] for line in str(claim.get("context_text") or "").splitlines()
               if (match := _WAITING_ROW.fullmatch(_plain(line)))]
    if not actions or any(action != "等待" for action in actions):
        return None
    snapshot = safe_mapping_dict(snapshot) or {}
    context = safe_mapping_dict(snapshot.get("rerun_context")) or {}
    identities = {str(value).strip() for value in (snapshot.get("pipeline"), context.get("pipeline_id")) if value}
    if identities != {"v2"}:
        return None
    outputs = safe_mapping_dict(context.get("structured_outputs")) or {}
    output = safe_mapping_dict(outputs.get("16", outputs.get(16))) or {}
    plan = safe_mapping_dict(output.get("position_plan")) or {}
    parsed = safe_mapping_dict(context.get("parsed")) or {}
    if (plan != parsed.get("position_plan") or plan.get("action") != "等待"
            or plan.get("planning_context") != "unassessed"
            or not _ZERO_PERCENT.fullmatch(str(plan.get("position_size") or "").strip())):
        return None
    evidence = safe_mapping_dict(plan.get("sizing_evidence")) or {}
    receipt = safe_mapping_dict(output.get("position_sizing_assessment")) or {}
    calculation = safe_mapping_dict(receipt.get("calculation")) or {}
    if (evidence.get("status") != "unassessed"
            or evidence.get("position_state", "unknown") != "unknown"
            or evidence.get("scenario_type", "unassessed") != "unassessed"
            or receipt.get("contract_version") != "position-sizing:v1"
            or receipt.get("status") != "unassessed" or receipt.get("issues") != []
            or calculation.get("status") != "unassessed" or calculation.get("position_state") != "unknown"
            or calculation.get("scenario_type") != "unassessed"
            or any(evidence.get(field) is not None for field in _CALCULATION_UNKNOWN_FIELDS)
            or any(calculation.get(field) is not None for field in _CALCULATION_UNKNOWN_FIELDS)):
        return None
    if _conflicting_policy_text(output.get("analysis_markdown")):
        return None
    from position_sizing_runtime import assess_position_plan

    checked = assess_position_plan(plan, context, output.get("recommendation"), output.get("analysis_markdown"))
    if checked.get("issues") or checked.get("status") != "unassessed":
        return None
    return {
        **claim, "claim_type": "execution_policy", "financial_evidence": False,
        "status": "valid", "verification_reason_code": "verified_waiting_position_policy",
        "matched_path": "rerun_context.structured_outputs.16.position_sizing_assessment",
        "matched_value": 0.0, "diff_pct": 0.0, "candidate_count": 1,
        "verification_scope": "research_no_new_position_only_not_account_holdings",
    }
