"""Read-only current-rule projections for persisted report snapshots."""

from __future__ import annotations

from typing import Any

from data_validation_values import safe_float
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text

from .content_credibility import evaluate_content_credibility
from .content_credibility_evidence_confidence import evaluate_confidence_evidence_alignment
from .content_credibility_inputs import confidence_score as recommendation_confidence_score


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


def project_evidence_confidence_alignment(snapshot: Any, recorded: Any) -> dict[str, Any] | None:
    """Refresh the evidence-confidence check when full parsed context is absent."""
    snapshot_map = safe_mapping_dict(snapshot) or {}
    recorded_map = safe_mapping_dict(recorded) or {}
    evidence_gate = safe_mapping_dict(snapshot_map.get("evidence_exit_gate")) or {}
    if not evidence_gate or not recorded_map:
        return None

    confidence = None
    for check in safe_dict_list(recorded_map.get("checks")):
        if safe_text(check.get("id")).strip() != "confidence_evidence_alignment":
            continue
        details = safe_mapping_dict(check.get("details")) or {}
        confidence = safe_float(details.get("confidence_score"))
        if confidence is not None:
            break
    if confidence is None:
        rerun_context = safe_mapping_dict(snapshot_map.get("rerun_context")) or {}
        parsed = safe_mapping_dict(rerun_context.get("parsed")) or {}
        recommendation = safe_mapping_dict(parsed.get("recommendation")) or {}
        confidence = recommendation_confidence_score(recommendation)

    alignment = evaluate_confidence_evidence_alignment(evidence_gate.get("verdict"), confidence)
    blocking = alignment["blocking_issues"]
    warnings = alignment["warnings"]
    status = "blocked" if blocking else "warning" if warnings else "passed"
    summary = {
        "blocked": "報告關鍵結論與資料或證據存在阻斷矛盾。",
        "warning": "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。",
        "passed": "報告關鍵結論通過內容可信度檢查。",
    }[status]
    return {
        "status": status,
        "summary": summary,
        "blocking_issues": blocking,
        "warnings": warnings,
        "checks": alignment["checks"],
    }


def project_content_credibility_with_current_evidence(
    snapshot: Any,
    recorded: Any,
    *,
    evidence_projection: Any,
) -> dict[str, Any] | None:
    """Merge the current evidence check even when full parsed context is unavailable."""
    projection_snapshot = dict(snapshot, evidence_exit_gate=evidence_projection) if evidence_projection is not None else snapshot
    projected = project_content_credibility(projection_snapshot)
    if evidence_projection is None:
        return projected
    alignment = project_evidence_confidence_alignment(projection_snapshot, recorded)
    if not alignment:
        return projected
    if projected:
        return merge_content_credibility_results(projected, alignment)
    return {**alignment, "_projection_scope": "evidence_confidence"}


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
    result["checks"] = _merge_checks(projected_map.get("checks"), recorded_map.get("checks"))
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


def _merge_checks(projected: Any, recorded: Any) -> list[dict[str, Any]]:
    """Prefer the current projection when it reports the same deterministic check id."""
    merged: list[dict[str, Any]] = []
    known_ids: set[str] = set()
    known_unidentified: set[tuple[str, str]] = set()
    for check in (*safe_dict_list(projected), *safe_dict_list(recorded)):
        check_id = safe_text(check.get("id")).strip()
        if check_id:
            if check_id in known_ids:
                continue
            known_ids.add(check_id)
        else:
            key = (check_id, safe_text(check.get("message")))
            if key in known_unidentified:
                continue
            known_unidentified.add(key)
        merged.append(check)
    return merged


__all__ = [
    "merge_content_credibility_results",
    "project_content_credibility",
    "project_content_credibility_with_current_evidence",
    "project_evidence_confidence_alignment",
]
