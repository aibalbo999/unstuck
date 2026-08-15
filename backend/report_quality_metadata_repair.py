"""Repair item builder for missing persisted report quality metadata."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text


def quality_metadata_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    snapshot_integrity = safe_mapping_dict(dict.get(report, "snapshot_integrity", {})) or {}
    if safe_text(dict.get(snapshot_integrity, "status")).strip().lower() != "verified":
        return None
    missing = [
        gate_key
        for gate_key in ("report_conformance", "evidence_exit_gate", "content_credibility")
        if not _quality_gate_recorded(dict.get(report, gate_key))
    ]
    if not missing:
        return None
    refreshed_from_report = safe_text(dict.get(report, "refreshed_from_report")).strip()
    if refreshed_from_report:
        title = "刷新後品質證據缺口"
        detail = (
            f"資料快照曾在報告後刷新（{refreshed_from_report}），但未保留 {'、'.join(missing)} 品質證據；"
            "採用前需人工查看 artifact 與 freshness。"
        )
        reason_codes = ["quality_metadata_missing", "quality_metadata_after_refresh"]
    else:
        title = "品質證據未記錄"
        detail = f"報告未記錄 {'、'.join(missing)} 品質證據，採用前需人工查看。"
        reason_codes = ["quality_metadata_missing"]
    return {
        "severity": "blocked",
        "priority_score": 820,
        "recommended_action": "manual_review",
        "action_label": "人工審核",
        "title": title,
        "detail": detail,
        "reason_codes": reason_codes,
        "blocks_auto_rerun": True,
    }


def _quality_gate_recorded(value: Any) -> bool:
    gate = safe_mapping_dict(value) or {}
    return bool(
        safe_text(dict.get(gate, "status")).strip()
        or safe_text(dict.get(gate, "verdict")).strip()
    )
