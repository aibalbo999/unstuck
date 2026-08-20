"""Repair item builder for missing persisted report quality metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mapping_fields import safe_mapping_dict, safe_text, safe_text_list


RECORDED_GATE_STATES: dict[str, tuple[str, frozenset[str]]] = {
    "report_conformance": ("status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
    "evidence_exit_gate": ("verdict", frozenset({"approved", "caution", "rejected"})),
    "content_credibility": ("status", frozenset({"passed", "warning", "blocked", "failed", "rejected"})),
}
QUALITY_METADATA_PROVENANCE = ("before_refresh", "after_refresh", "no_refresh_provenance")


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
    refresh_provenance = safe_mapping_dict(
        dict.get(report_payload, "quality_metadata_refresh_provenance", {})
    )
    before_missing_fields = set(
        safe_text_list(dict.get(refresh_provenance or {}, "missing_fields"))
    )
    if refreshed_from_report:
        if refresh_provenance is not None and set(missing).issubset(before_missing_fields):
            title = "刷新前已有品質證據缺口"
            detail = (
                f"資料快照曾在報告後刷新（{refreshed_from_report}），刷新前快照已確認缺少 {'、'.join(missing)} 品質證據；"
                "資料刷新保留既有品質 gate，沒有重新執行品質檢查；採用前需安排完整重跑並人工查看 artifact 與 freshness。"
            )
            reason_codes = ["quality_metadata_missing", "quality_metadata_before_refresh"]
        else:
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
    if refresh_provenance:
        item["quality_metadata_refresh_provenance"] = refresh_provenance
    if refreshed_from_report:
        rerun_context_status = _rerun_context_status(report_payload)
        artifact_rerun_context_status = safe_text(
            dict.get(report_payload, "artifact_rerun_context_status")
        ).strip().lower()
        if rerun_context_status in {"missing", "partial"} and artifact_rerun_context_status == "present":
            rerun_context_status = "artifact_fallback_available"
        item["rerun_context_status"] = rerun_context_status
        item["snapshot_rerun_context_status"] = _rerun_context_status(report_payload)
        if artifact_rerun_context_status:
            item["artifact_rerun_context_status"] = artifact_rerun_context_status
        rerun_execution_status = _rerun_execution_status(report_payload, rerun_context_status)
        item["rerun_execution_status"] = rerun_execution_status
        if rerun_context_status == "missing":
            item["detail"] += "目前沒有可供局部重跑的原始分析上下文；若資料標記需重跑，應安排完整重跑後再採用。"
            if (
                dict.get(report_payload, "refreshed_without_analysis_rerun")
                or safe_text(dict.get(report_payload, "decision_validity_status")).strip().lower() == "needs_rerun"
            ):
                item["reason_codes"].append("rerun_context_missing")
        elif rerun_context_status == "artifact_fallback_available":
            if rerun_execution_status == "full_rerun_required":
                item["detail"] += "snapshot 未保存可供局部重跑的原始分析上下文，但 Markdown artifact 已找到完整前序 Agent 段落；目前資料 freshness 仍要求完整重跑，不能以此上下文取代完整分析。"
            else:
                item["detail"] += "snapshot 未保存可供局部重跑的原始分析上下文，但 Markdown artifact 已找到完整前序 Agent 段落；可嘗試只重跑最終建議，仍需先核對 artifact 與 freshness。"
        elif rerun_context_status == "partial":
            item["detail"] += "目前只有部分原始分析上下文；局部重跑前需先確認前序 Agent 輸入是否完整。"
    return item


def quality_metadata_provenance_from_reason_codes(reason_codes: Any) -> str:
    codes = set(safe_text_list(reason_codes))
    if "quality_metadata_before_refresh" in codes:
        return "before_refresh"
    if "quality_metadata_after_refresh" in codes:
        return "after_refresh"
    return "no_refresh_provenance"


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


def _rerun_execution_status(report: Mapping[str, Any], rerun_context_status: str) -> str:
    report_payload = safe_mapping_dict(report) or {}
    decision_status = safe_text(dict.get(report_payload, "decision_validity_status")).strip().lower()
    if _safe_bool(dict.get(report_payload, "refreshed_without_analysis_rerun")) or decision_status == "needs_rerun":
        return "full_rerun_required"
    if rerun_context_status in {"present", "artifact_fallback_available"}:
        return "partial_rerun_available"
    if rerun_context_status == "partial":
        return "partial_rerun_review_required"
    return "partial_rerun_unavailable"


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False


__all__ = [
    "QUALITY_METADATA_PROVENANCE",
    "RECORDED_GATE_STATES",
    "quality_metadata_provenance_from_reason_codes",
    "quality_metadata_repair_item",
]
