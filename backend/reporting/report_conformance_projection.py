"""Read-only current quality-gate projections for persisted report conformance."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text


_STATUS_RANK = {"passed": 1, "warning": 2, "blocked": 3, "failed": 3, "rejected": 3}
_STATUS_SUMMARIES = {
    "passed": "報告符合輸出契約。",
    "warning": "報告符合主要輸出契約，但仍需人工注意警示。",
    "blocked": "報告未符合輸出契約，需修正後再採用。",
}


def _gate_step(step_id: str, gate: dict, *, label: str) -> dict:
    status = safe_text(gate.get("status") or gate.get("verdict")).strip().lower()
    if step_id == "evidence_exit_gate":
        status = "blocked" if status == "rejected" else "passed" if status == "approved" else "warning"
        messages = {
            "passed": "證據抽查通過。",
            "warning": "證據抽查未完全通過。",
            "blocked": "證據抽查拒絕報告數字。",
        }
    else:
        status = "blocked" if status in {"blocked", "failed", "rejected"} else "passed" if status == "passed" else "warning"
        messages = {
            "passed": "內容可信度檢查通過。",
            "warning": "內容可信度檢查有警示。",
            "blocked": "內容可信度檢查發現阻斷矛盾。",
        }
    return {"id": step_id, "status": status, "message": messages[status], "details": {label: gate}}


def _merge_issues(existing: Any, additions: list[dict[str, Any]], *, resolved: set[str]) -> list[dict[str, Any]]:
    merged = [item for item in safe_dict_list(existing) if safe_text(item.get("id")) not in resolved]
    known = {(safe_text(item.get("id")), safe_text(item.get("message"))) for item in merged}
    for item in additions:
        key = (safe_text(item.get("id")), safe_text(item.get("message")))
        if key not in known:
            merged.append(item)
            known.add(key)
    return merged


def project_report_conformance(recorded: Any, evidence_exit_gate: Any, content_credibility: Any) -> dict[str, Any]:
    """Project current evidence/content statuses without mutating persisted conformance."""
    recorded_map = safe_mapping_dict(recorded) or {}
    evidence_map = safe_mapping_dict(evidence_exit_gate) or {}
    content_map = safe_mapping_dict(content_credibility) or {}
    if not evidence_map and not content_map:
        return recorded_map

    steps = safe_dict_list(recorded_map.get("decision_tree"))
    projected_steps = []
    replaced = set()
    for item in steps:
        step_id = safe_text(item.get("id")).strip()
        if step_id == "evidence_exit_gate" and evidence_map:
            projected_steps.append(_gate_step(step_id, evidence_map, label="evidence_exit_gate"))
            replaced.add(step_id)
        elif step_id == "content_credibility" and content_map:
            projected_steps.append(_gate_step(step_id, content_map, label="content_credibility"))
            replaced.add(step_id)
        else:
            projected_steps.append(item)
    if evidence_map and "evidence_exit_gate" not in replaced:
        projected_steps.append(_gate_step("evidence_exit_gate", evidence_map, label="evidence_exit_gate"))
    if content_map and "content_credibility" not in replaced:
        projected_steps.append(_gate_step("content_credibility", content_map, label="content_credibility"))

    # Only an explicitly recomputed, passing gate can resolve its old finding.
    # Other findings and unexplained historical severity remain visible.
    supplied = {name for name, gate in (("evidence_exit_gate", evidence_map),
                                      ("content_credibility", content_map)) if gate}
    resolved = {step["id"] for step in projected_steps
                if step.get("id") in supplied and step.get("status") == "passed"}
    old_blocking = safe_dict_list(recorded_map.get("blocking_issues"))
    old_warnings = safe_dict_list(recorded_map.get("warnings"))
    old_findings = old_blocking + old_warnings + [step for step in steps
                    if _STATUS_RANK.get(safe_text(step.get("status")), 0) > 1]
    resolved_recorded = any(safe_text(item.get("id")) in resolved for item in old_findings)
    explained_rank = max([3 if old_blocking else 0, 2 if old_warnings else 0]
                         + [_STATUS_RANK.get(safe_text(step.get("status")), 0) for step in steps])

    current_blocking = [
        {"id": safe_text(step.get("id")), "message": safe_text(step.get("message")), "details": step.get("details", {})}
        for step in projected_steps
        if step.get("status") in {"blocked", "failed", "rejected"}
    ]
    current_warnings = [
        {"id": safe_text(step.get("id")), "message": safe_text(step.get("message")), "details": step.get("details", {})}
        for step in projected_steps
        if step.get("status") == "warning"
    ]
    recorded_status = safe_text(recorded_map.get("status")).strip().lower()
    result = dict(recorded_map)
    result["schema_version"] = recorded_map.get("schema_version", 1)
    result["decision_tree"] = projected_steps
    result["blocking_issues"] = _merge_issues(old_blocking, current_blocking, resolved=resolved)
    result["warnings"] = _merge_issues(old_warnings, current_warnings, resolved=resolved)
    current_status = "blocked" if result["blocking_issues"] else "warning" if result["warnings"] else "passed"
    status = current_status if resolved_recorded and _STATUS_RANK.get(recorded_status, 0) <= explained_rank else max(
        (recorded_status, current_status), key=lambda value: _STATUS_RANK.get(value, 0))
    result["status"] = status
    result["summary"] = _STATUS_SUMMARIES.get(status, safe_text(recorded_map.get("summary")))
    return result


def report_conformance_projection_metadata(recorded: Any, projected: Any) -> dict[str, str] | None:
    recorded_map = safe_mapping_dict(recorded) or {}
    projected_map = safe_mapping_dict(projected) or {}
    if not projected_map or projected_map == recorded_map:
        return None
    return {
        "status": "projected",
        "source": "snapshot.current_evidence_and_content",
        "persisted_status": safe_text(recorded_map.get("status")).strip().lower(),
    }


__all__ = ["project_report_conformance", "report_conformance_projection_metadata"]
