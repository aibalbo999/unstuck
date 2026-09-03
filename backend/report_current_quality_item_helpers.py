"""Pure item and status helpers for current-quality projections."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
from report_freshness_summary import report_freshness_bucket, safe_bool
from report_pipeline_identity import resolve_report_pipeline_id


def conformance_status(value: Any) -> str:
    status = safe_text((safe_mapping_dict(value) or {}).get("status")).strip().lower()
    if status in {"blocked", "failed", "rejected"}:
        return "blocked"
    return status if status in {"passed", "warning"} else "unknown"


def content_status(value: Any) -> str:
    status = safe_text((safe_mapping_dict(value) or {}).get("status")).strip().lower()
    if status in {"blocked", "failed", "rejected"}:
        return "blocked"
    return status if status in {"passed", "warning"} else "unknown"


def evidence_verdict(value: Any) -> str:
    verdict = safe_text((safe_mapping_dict(value) or {}).get("verdict")).strip().lower()
    return verdict if verdict in {"approved", "caution", "rejected"} else "unknown"


def evidence_reason_counts(value: Any) -> dict[str, int]:
    gate = safe_mapping_dict(value) or {}
    raw_counts = safe_mapping_dict(gate.get("unverifiable_reason_counts")) or {}
    return {
        reason: count
        for raw_reason, raw_count in raw_counts.items()
        if (reason := safe_text(raw_reason).strip())
        and (count := safe_int(raw_count, default=0)) > 0
    }


def evidence_unverifiable_count(
    value: Any,
    reason_counts: dict[str, int] | None = None,
) -> int:
    counts = reason_counts if reason_counts is not None else evidence_reason_counts(value)
    reason_total = sum(counts.values())
    gate = safe_mapping_dict(value) or {}
    recorded_count = max(0, safe_int(gate.get("unverifiable_count"), default=0))
    return max(recorded_count, reason_total)


def evidence_failed_count(value: Any) -> int:
    gate = safe_mapping_dict(value) or {}
    return max(0, safe_int(gate.get("failed_count"), default=0))


def blocker_ids(value: Any, *, include_decision_tree: bool = False) -> set[str]:
    gate = safe_mapping_dict(value) or {}
    blocker_ids = {
        safe_text(issue.get("id")).strip() or "unknown"
        for issue in safe_dict_list(gate.get("blocking_issues"))
    }
    if include_decision_tree:
        blocker_ids.update(
            safe_text(step.get("id")).strip() or "unknown"
            for step in safe_dict_list(gate.get("decision_tree"))
            if safe_text(step.get("status")).strip().lower() in {"blocked", "failed", "rejected"}
        )
    elif not blocker_ids:
        blocker_ids.update(
            safe_text(check.get("id")).strip() or "unknown"
            for check in safe_dict_list(gate.get("checks"))
            if safe_text(check.get("status")).strip().lower() in {"blocked", "failed", "rejected"}
        )
    return blocker_ids


def blocker_messages(value: Any) -> list[str]:
    gate = safe_mapping_dict(value) or {}
    messages: list[str] = []
    seen: set[str] = set()
    for issue in safe_dict_list(gate.get("blocking_issues")):
        details = safe_mapping_dict(issue.get("details")) or {}
        candidates = safe_text_list(details.get("critical")) or [safe_text(issue.get("message"))]
        for candidate in candidates:
            message = safe_text(candidate).strip()
            if message and message not in seen:
                messages.append(message)
                seen.add(message)
    return messages


def current_quality_item(
    report: dict[str, Any],
    conformance: str,
    content: str,
    evidence: str,
    *,
    quality_action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conformance_payload = safe_mapping_dict(report.get("report_conformance")) or {}
    failed_count = evidence_failed_count(report.get("evidence_exit_gate"))
    reason_counts = evidence_reason_counts(report.get("evidence_exit_gate"))
    unverifiable_count = evidence_unverifiable_count(
        report.get("evidence_exit_gate"),
        reason_counts,
    )
    content_blockers = sorted(blocker_ids(report.get("content_credibility")))
    content_messages = blocker_messages(report.get("content_credibility"))
    issues = safe_dict_list(conformance_payload.get("blocking_issues")) + safe_dict_list(conformance_payload.get("warnings"))
    reason = next(
        (
            safe_text(issue.get("message") or issue.get("detail")).strip()
            for issue in issues
            if safe_text(issue.get("message") or issue.get("detail")).strip()
        ),
        "目前品質狀態需要人工查看。",
    )
    filename = safe_text(report.get("filename")).strip() or safe_text(report.get("report_filename")).strip()
    payload = {
        "ticker": safe_text(report.get("ticker")).strip(),
        "pipeline_id": resolve_report_pipeline_id(
            filename,
            stored_pipeline=report.get("pipeline_id"),
        ),
        "filename": filename,
        "report_date": safe_text(report.get("date") or report.get("report_date")).strip(),
        "report_conformance_status": conformance,
        "content_credibility_status": content,
        "evidence_exit_gate_verdict": evidence,
        "evidence_failed_count": failed_count,
        "evidence_unverifiable_count": unverifiable_count,
        "evidence_unverifiable_reason_counts": reason_counts,
        "content_credibility_blocker_ids": content_blockers,
        "content_credibility_blocker_messages": content_messages,
        "reason": reason,
    }
    if quality_action:
        payload["quality_action"] = {
            "recommended_action": safe_text(quality_action.get("recommended_action")).strip() or "unknown",
            "action_label": safe_text(quality_action.get("action_label")).strip() or "人工審核",
            "title": safe_text(quality_action.get("title")).strip() or "品質狀態需要處理",
            "detail": safe_text(quality_action.get("detail")).strip() or "品質 gate 需要人工確認。",
            "reason_codes": safe_text_list(quality_action.get("reason_codes")),
            "blocks_auto_rerun": safe_bool(quality_action.get("blocks_auto_rerun")),
        }
    freshness = report_freshness_bucket(report)
    if failed_count:
        payload["evidence_mismatch_freshness_status"] = freshness
    if unverifiable_count:
        payload["evidence_unverifiable_freshness_status"] = freshness
    if content_blockers:
        payload["content_credibility_freshness_status"] = freshness
    return payload


def status_rank(status: str) -> int:
    return {"blocked": 0, "warning": 1, "unknown": 2, "passed": 3}.get(status, 2)


def quality_attention_rank(item: dict[str, Any]) -> int:
    evidence_rank = {"rejected": 0, "caution": 1, "unknown": 2, "approved": 3}.get(
        item.get("evidence_exit_gate_verdict"),
        2,
    )
    return min(
        status_rank(item.get("report_conformance_status", "unknown")),
        status_rank(item.get("content_credibility_status", "unknown")),
        evidence_rank,
    )


def quality_attention_sort_key(
    item: dict[str, Any],
    quality_action: dict[str, Any] | None,
) -> tuple[int, int, str]:
    priority = safe_int((quality_action or {}).get("priority_score"), default=0)
    return (quality_attention_rank(item), -priority, item["filename"])
