"""Safe display of additive role contracts; never validates or invents evidence."""
from mapping_fields import safe_mapping_dict
from trade_catalyst_semantics import normalize_trade_catalyst_fields

from .html_sanitizer import sanitize_report_plain_text


def _clean(value):
    if isinstance(value, str):
        return sanitize_report_plain_text(value)
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def sanitized_trade_semantics(setup):
    return _clean(normalize_trade_catalyst_fields(setup))


def trade_semantic_rows(setup):
    fields = sanitized_trade_semantics(setup)
    rows = []
    def add(label, value):
        rows.append({"label": label, "value": value})
    if "observed_signal" in fields:
        add("已觀測訊號", fields["observed_signal"] or "未評估")
    if "event_catalyst" in fields:
        event = fields["event_catalyst"] or {}
        if event.get("date") and event.get("status") != "unknown":
            status = {"scheduled": "排定", "confirmed": "已確認", "date_range": "日期範圍"}.get(event["status"], "未確認")
            date_text = event["date"] + (f" 至 {event['end_date']}" if event.get("end_date") else "")
            event_text = f"{event.get('description') or '未評估'}；{date_text}；{status}；時區 {event.get('timezone') or '未確認'}"
        else:
            event_text = "事件日期未確認"
        add("事件催化", event_text)
    if "recheck_condition" in fields:
        add("重新評估條件", fields["recheck_condition"] or "未評估")
    if fields.get("financial_risk_flags"):
        add("財務風險", "；".join(fields["financial_risk_flags"]))
    return rows


def sanitized_position_basis(plan):
    from pydantic import ValidationError
    from structured_output_position_sizing import PositionSizingEvidence
    result = {}
    if "planning_context" in plan:
        raw = plan.get("planning_context")
        result["planning_context"] = raw if isinstance(raw, str) and raw in {"research", "actual", "unassessed"} else "unassessed"
    if "sizing_evidence" in plan:
        result["sizing_evidence"] = None
        receipt = safe_mapping_dict(plan.get("sizing_evidence"))
        if receipt:
            try:
                result["sizing_evidence"] = _clean(PositionSizingEvidence.model_validate(receipt).model_dump())
            except (ValidationError, ValueError, TypeError):
                pass
    return result


def position_basis_rows(plan):
    context = plan.get("planning_context")
    basis = {"research": "明確研究假設", "actual": "明確實際輸入"}.get(context, "未評估，未取得資金與持倉輸入") if isinstance(context, str) else "未評估，未取得資金與持倉輸入"
    rows = [{"label": "部位基準", "value": basis}]
    if plan.get("action") == "等待" or plan.get("position_size") == "0%":
        rows.append({"label": "比例意義", "value": "0% 僅指本研究不新增部位，不代表使用者實際持倉為零。"})
    receipt = sanitized_position_basis(plan).get("sizing_evidence") or {}
    if receipt.get("status") == "calculated":
        rows.append({"label": "比例計算依據", "value": f"資金 {receipt.get('capital_amount')} {receipt.get('currency') or ''}；風險預算 {receipt.get('risk_budget_amount')}；{receipt.get('formula') or '公式未提供'}；來源 {receipt.get('source_ref') or '未提供'}"})
    return rows
