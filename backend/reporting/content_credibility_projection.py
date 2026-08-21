"""Read-only current-rule projections for persisted report snapshots."""

from __future__ import annotations

from typing import Any

from data_validation_values import safe_float
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text

from .content_credibility import evaluate_content_credibility
from .content_credibility_evidence_confidence import evaluate_confidence_evidence_alignment
from .content_credibility_inputs import confidence_score as recommendation_confidence_score


_STATUS_RANK = {"passed": 1, "warning": 2, "blocked": 3, "failed": 3, "rejected": 3}
_STATUS_SUMMARIES = {
    "passed": "報告關鍵結論通過內容可信度檢查。",
    "warning": "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。",
    "blocked": "報告關鍵結論與資料或證據存在阻斷矛盾。",
}
_TRADE_SETUP_ISSUE_IDS = frozenset(
    {
        "invalid_trade_direction",
        "missing_trade_setup_price_inputs",
        "ambiguous_trade_setup_price_inputs",
        "long_target_not_above_current_price",
        "long_stop_not_below_current_price",
        "short_target_not_below_current_price",
        "short_stop_not_above_current_price",
    }
)
_EVIDENCE_ALIGNMENT_ISSUE_IDS = frozenset({"high_confidence_rejected_evidence", "high_confidence_unrecorded_evidence", "non_approved_evidence_gate"})


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

    alignment = evaluate_confidence_evidence_alignment(evidence_gate.get("verdict"), confidence, evidence_gate)
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
    recommendation: Any = None,
) -> dict[str, Any] | None:
    """Merge the current evidence check even when full parsed context is unavailable."""
    projection_snapshot = dict(snapshot, evidence_exit_gate=evidence_projection) if evidence_projection is not None else snapshot
    projected = project_content_credibility(projection_snapshot)
    if projected is None:
        projected = _project_from_index_recommendation(projection_snapshot, recommendation)
    if evidence_projection is None:
        return projected
    alignment = project_evidence_confidence_alignment(projection_snapshot, recorded)
    if not alignment:
        return projected
    if projected:
        return merge_content_credibility_results(projected, alignment)
    return {**alignment, "_projection_scope": "evidence_confidence"}


def _project_from_index_recommendation(snapshot: Any, recommendation: Any) -> dict[str, Any] | None:
    """Project legacy reports from the normalized index recommendation when parsed context is absent."""
    snapshot_map = safe_mapping_dict(snapshot) or {}
    recommendation_map = safe_mapping_dict(recommendation) or {}
    pipeline_id = safe_text(snapshot_map.get("pipeline")).strip().lower()
    if pipeline_id == "v4" or not recommendation_map or not snapshot_map.get("data"):
        return None
    label = safe_text(recommendation_map.get("recommendation")).strip()
    if not label or label.upper() in {"N/A", "NA", "UNKNOWN"}:
        return None

    parsed_recommendation = {"建議": label}
    aliases = {
        "confidence": "信心",
        "target_3m": "3個月",
        "target_6m": "6個月",
        "target_12m": "12個月",
    }
    for source, target in aliases.items():
        value = recommendation_map.get(source)
        if value not in (None, "", "N/A"):
            parsed_recommendation[target] = value

    context = {
        "pipeline_id": pipeline_id,
        "data": safe_mapping_dict(snapshot_map.get("data")) or {},
        "parsed": {"recommendation": parsed_recommendation},
        "evidence_exit_gate": safe_mapping_dict(snapshot_map.get("evidence_exit_gate")) or {},
        "final_audit": safe_mapping_dict(snapshot_map.get("final_audit")) or {},
    }
    # Legacy snapshots may contain an empty matrix even though their canonical
    # source audit still has enough data to build the current recommendation row.
    projection_snapshot = dict(snapshot_map)
    if not safe_sequence_items(projection_snapshot.get("evidence_matrix")):
        projection_snapshot.pop("evidence_matrix", None)
    try:
        projected = evaluate_content_credibility(context, projection_snapshot)
    except Exception:
        return None
    return {**projected, "_projection_scope": "recommendation_context"}


def merge_content_credibility_results(recorded: Any, projected: Any) -> dict[str, Any]:
    """Merge a read-only projection without hiding previously recorded findings."""
    recorded_map = safe_mapping_dict(recorded) or {}
    projected_map = safe_mapping_dict(projected) or {}
    if not projected_map:
        return recorded_map
    if not recorded_map:
        return projected_map

    resolved_issue_ids = _resolved_trade_setup_issue_ids(projected_map)
    result = dict(recorded_map)
    result.update(
        {
            key: value
            for key, value in projected_map.items()
            if key not in {"blocking_issues", "warnings", "checks", "status", "summary", "_projection_scope"}
        }
    )
    result["blocking_issues"] = _merge_issues(
        projected_map.get("blocking_issues"),
        recorded_map.get("blocking_issues"),
        suppressed_ids=resolved_issue_ids,
    )
    result["warnings"] = _merge_issues(
        projected_map.get("warnings"),
        recorded_map.get("warnings"),
        suppressed_ids=resolved_issue_ids,
    )
    result["checks"] = _merge_checks(projected_map.get("checks"), recorded_map.get("checks"))
    recorded_status = safe_text(recorded_map.get("status")).strip().lower()
    projected_status = safe_text(projected_map.get("status")).strip().lower()
    if resolved_issue_ids and not result["blocking_issues"] and not result["warnings"]:
        status = projected_status
    else:
        status = max((recorded_status, projected_status), key=lambda value: _STATUS_RANK.get(value, 0))
    if status:
        result["status"] = status
        result["summary"] = _STATUS_SUMMARIES.get(status, safe_text(projected_map.get("summary")).strip())
    return result


def _resolved_trade_setup_issue_ids(projected: dict[str, Any]) -> frozenset[str]:
    resolved: set[str] = set()
    for check in safe_dict_list(projected.get("checks")):
        if (
            safe_text(check.get("id")).strip() == "trade_setup_alignment"
            and safe_text(check.get("status")).strip().lower() == "passed"
        ):
            resolved.update(_TRADE_SETUP_ISSUE_IDS)
        details = safe_mapping_dict(check.get("details")) or {}
        if (
            safe_text(check.get("id")).strip() == "confidence_evidence_alignment"
            and safe_text(check.get("status")).strip().lower() == "passed"
            and safe_text(details.get("evidence_verdict")).strip().lower() == "approved"
        ):
            resolved.update(_EVIDENCE_ALIGNMENT_ISSUE_IDS)
    return frozenset(resolved)


def _merge_issues(*values: Any, suppressed_ids: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    known: set[tuple[str, str]] = set()
    for value in values:
        for issue in safe_dict_list(value):
            issue_id = safe_text(issue.get("id"))
            if issue_id in suppressed_ids:
                continue
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
