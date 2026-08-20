"""Repair item builder for missing persisted report quality metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mapping_fields import safe_mapping_dict, safe_text


RECORDED_GATE_STATES: dict[str, tuple[str, frozenset[str]]] = {
    "report_conformance": ("status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
    "evidence_exit_gate": ("verdict", frozenset({"approved", "caution", "rejected"})),
    "content_credibility": ("status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
}


def quality_metadata_repair_item(report: Mapping[str, Any]) -> dict[str, Any] | None:
    report_payload = safe_mapping_dict(report) or {}
    snapshot_integrity = safe_mapping_dict(dict.get(report_payload, "snapshot_integrity", {})) or {}
    if safe_text(dict.get(snapshot_integrity, "status")).strip().lower() != "verified":
        return None
    missing = [
        gate_key
        for gate_key in ("report_conformance", "evidence_exit_gate", "content_credibility")
        if not _quality_gate_recorded(gate_key, dict.get(report_payload, gate_key))
    ]
    if not missing:
        return None
    refreshed_from_report = safe_text(dict.get(report_payload, "refreshed_from_report")).strip()
    if refreshed_from_report:
        title = "刷新後品質證據缺口"
        detail = (
            f"資料快照曾在報告後刷新（{refreshed_from_report}），目前未記錄 {'、'.join(missing)} 品質證據；"
            "刷新歸因存在，但無法由目前 metadata 判定缺口是否由刷新造成；"
            "採用前需人工查看 artifact 與 freshness。"
        )
        reason_codes = ["quality_metadata_missing", "quality_metadata_after_refresh"]
    else:
        title = "品質證據未記錄"
        detail = f"報告未記錄 {'、'.join(missing)} 品質證據，採用前需人工查看。"
        reason_codes = ["quality_metadata_missing"]
    item = {
        "severity": "blocked",
        "priority_score": 820,
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": title,
        "detail": detail,
        "missing_quality_fields": missing,
        "reason_codes": reason_codes,
        "blocks_auto_rerun": True,
    }
    if refreshed_from_report:
        rerun_context_status = _rerun_context_status(report_payload)
        item["rerun_context_status"] = rerun_context_status
        if rerun_context_status == "missing":
            item["detail"] += "目前沒有可供局部重跑的原始分析上下文；若資料標記需重跑，應安排完整重跑後再採用。"
            if (
                dict.get(report_payload, "refreshed_without_analysis_rerun")
                or safe_text(dict.get(report_payload, "decision_validity_status")).strip().lower() == "needs_rerun"
            ):
                item["reason_codes"].append("rerun_context_missing")
        elif rerun_context_status == "partial":
            item["detail"] += "目前只有部分原始分析上下文；局部重跑前需先確認前序 Agent 輸入是否完整。"
    return item


def _quality_gate_recorded(gate_key: str, value: Any) -> bool:
    gate = safe_mapping_dict(value) or {}
    field_name, allowed_states = RECORDED_GATE_STATES[gate_key]
    return safe_text(dict.get(gate, field_name)).strip().lower() in allowed_states


def _rerun_context_status(report: Mapping[str, Any]) -> str:
    report_payload = safe_mapping_dict(report) or {}
    rerun_context = safe_mapping_dict(dict.get(report_payload, "rerun_context", {})) or {}
    available_fields = sum(
        bool(safe_mapping_dict(dict.get(rerun_context, field, {})) or {})
        for field in ("analyses", "structured_outputs", "parsed")
    )
    if available_fields == 3:
        return "present"
    if available_fields > 0:
        return "partial"
    return "missing"
