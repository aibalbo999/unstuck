"""Provider-impact action item shaping for the daily decision queue."""

from __future__ import annotations

from typing import Any

from daily_decision_report_keys import report_key
from mapping_fields import mapping_field as _field
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


def provider_impact_items(ledger: dict[str, Any], *, skip_keys: set[str]) -> list[dict[str, Any]]:
    payload = safe_mapping_dict(ledger) or {}
    items = []
    for row in safe_dict_list(_field(payload, "items")):
        if not isinstance(row, dict) or report_key(row) in skip_keys:
            continue
        summary = safe_mapping_dict(_field(row, "summary")) or {}
        blocks = _bool(_field(summary, "blocks_auto_rerun"))
        if not blocks:
            continue
        action = safe_text(_field(summary, "recommended_action")).strip() or "wait_provider_recovery"
        filename = safe_text(_field(row, "filename")).strip() or safe_text(_field(row, "report_filename")).strip() or None
        ticker = safe_text(_field(row, "ticker")).strip()
        pipeline_id = safe_text(_field(row, "pipeline_id")).strip() or "v1"
        items.append({
            "source": "provider_impact",
            "type": "wait_provider_recovery" if blocks else "monitor_provider",
            "priority_score": 900 if blocks else 520,
            "title": f"{ticker or '報告'} provider 影響需處理",
            "detail": _provider_detail(row, blocks),
            "ticker": ticker,
            "filename": filename,
            "report_filename": filename,
            "pipeline_id": pipeline_id,
            "recommended_action": action,
            "blocks_auto_rerun": blocks,
        })
    return items


def _provider_detail(row: dict[str, Any], blocks: bool) -> str:
    message = next((text for item in safe_dict_list(_field(row, "impacts")) if (text := safe_text(_field(item, "message")).strip())), "")
    if message:
        return message
    if blocks:
        return "核心來源不穩，先等待 provider recovery，避免盲目重跑。"
    return "來源有警示但未阻擋核心資料，列為監控。"


def _bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return False


__all__ = ["provider_impact_items"]
