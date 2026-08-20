"""Read-only current-rule projections for persisted report snapshots."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text

from .content_credibility import evaluate_content_credibility


_STATUS_RANK = {"passed": 1, "warning": 2, "blocked": 3, "failed": 3, "rejected": 3}
_STATUS_SUMMARIES = {
    "passed": "報告關鍵結論通過內容可信度檢查。",
    "warning": "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。",
    "blocked": "報告關鍵結論與資料或證據存在阻斷矛盾。",
}


def project_content_credibility(snapshot: Any) -> dict[str, Any] | None:
    """Evaluate current deterministic rules when a snapshot saved parsed context."""
    snapshot_map = safe_mapping_dict(snapshot) or {}
    rerun_context = safe_mapping_dict(snapshot_map.get("rerun_context")) or {}
    parsed = safe_mapping_dict(rerun_context.get("parsed")) or {}
    data = safe_mapping_dict(snapshot_map.get("data")) or {}
    pipeline_id = safe_text(rerun_context.get("pipeline_id") or snapshot_map.get("pipeline")).strip().lower()
    if not parsed or not data or not pipeline_id:
        return None

    context = dict(rerun_context)
    context["pipeline_id"] = pipeline_id
    context["parsed"] = parsed
    context["data"] = data
    context.setdefault("evidence_exit_gate", snapshot_map.get("evidence_exit_gate", {}))
    context.setdefault("final_audit", snapshot_map.get("final_audit", {}))
    try:
        return evaluate_content_credibility(context, snapshot_map)
    except Exception:
        # Historical audit is read-only; malformed legacy context must not make it unavailable.
        return None


def merge_content_credibility_results(recorded: Any, projected: Any) -> dict[str, Any]:
    """Merge a read-only projection without hiding previously recorded findings."""
    recorded_map = safe_mapping_dict(recorded) or {}
    projected_map = safe_mapping_dict(projected) or {}
    if not projected_map:
        return recorded_map
    if not recorded_map:
        return projected_map

    result = dict(recorded_map)
    result.update(
        {
            key: value
            for key, value in projected_map.items()
            if key not in {"blocking_issues", "warnings", "checks", "status", "summary"}
        }
    )
    result["blocking_issues"] = _merge_issues(recorded_map.get("blocking_issues"), projected_map.get("blocking_issues"))
    result["warnings"] = _merge_issues(recorded_map.get("warnings"), projected_map.get("warnings"))
    result["checks"] = _merge_issues(projected_map.get("checks"), recorded_map.get("checks"))
    recorded_status = safe_text(recorded_map.get("status")).strip().lower()
    projected_status = safe_text(projected_map.get("status")).strip().lower()
    status = max((recorded_status, projected_status), key=lambda value: _STATUS_RANK.get(value, 0))
    if status:
        result["status"] = status
        result["summary"] = _STATUS_SUMMARIES.get(status, safe_text(projected_map.get("summary")).strip())
    return result


def _merge_issues(*values: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    known: set[tuple[str, str]] = set()
    for value in values:
        for issue in safe_dict_list(value):
            issue_id = safe_text(issue.get("id"))
            message = safe_text(issue.get("message"))
            key = (issue_id, message)
            if key in known:
                continue
            merged.append(issue)
            known.add(key)
    return merged


__all__ = ["merge_content_credibility_results", "project_content_credibility"]
