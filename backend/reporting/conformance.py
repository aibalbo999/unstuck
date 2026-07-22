"""Decision-tree conformance checks for rendered reports."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict

from .conformance_steps import build_conformance_gate_steps
from .conformance_visibility import missing_visible_markers
from .mode_templates import get_report_template_profile


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _step(step_id: str, status: str, message: str, details: Any = None) -> dict:
    result = {"id": step_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def _issue(step: dict) -> dict:
    return {"id": step["id"], "message": step["message"], "details": dict.get(step, "details")}


def evaluate_report_conformance(
    html: str,
    markdown: str,
    *,
    context: dict | None = None,
    snapshot: dict | None = None,
    report_lint: dict | None = None,
    evidence_exit_gate: dict | None = None,
    content_credibility: dict | None = None,
) -> dict:
    """Evaluate whether rendered report artifacts satisfy the system output contract."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    report_lint = _as_dict(report_lint)
    evidence_exit_gate = _as_dict(evidence_exit_gate)
    raw_content_credibility = (
        content_credibility
        if content_credibility is not None
        else dict.get(context, "content_credibility") or dict.get(snapshot, "content_credibility")
    )
    content_credibility = _as_dict(raw_content_credibility)
    profile = get_report_template_profile(dict.get(context, "pipeline_id") or dict.get(snapshot, "pipeline") or "v1")
    gate_steps = build_conformance_gate_steps(
        context=context,
        snapshot=snapshot,
        report_lint=report_lint,
        evidence_exit_gate=evidence_exit_gate,
        content_credibility=content_credibility,
    )

    missing_markers = missing_visible_markers(html, markdown, profile)
    if missing_markers:
        step = _step("required_visibility", "blocked", "報告缺少必要可見段落。", missing_markers)
        visibility_blocks = [_issue(step)]
    else:
        step = _step("required_visibility", "passed", "必要段落已在 HTML 與 Markdown 顯示。")
        visibility_blocks = []
    report_lint_blocks = [issue for issue in gate_steps["blocking_issues"] if issue["id"] == "report_lint"]
    other_blocks = [issue for issue in gate_steps["blocking_issues"] if issue["id"] != "report_lint"]
    decision_tree = [gate_steps["decision_tree"][0], step, *gate_steps["decision_tree"][1:]]
    blocking_issues = [*report_lint_blocks, *visibility_blocks, *other_blocks]
    warnings = gate_steps["warnings"]

    if blocking_issues:
        status = "blocked"
        summary = "報告未符合輸出契約，需修正後再採用。"
    elif warnings:
        status = "warning"
        summary = "報告符合主要輸出契約，但仍需人工注意警示。"
    else:
        status = "passed"
        summary = "報告符合輸出契約。"

    return {
        "schema_version": 1,
        "status": status,
        "summary": summary,
        "decision_tree": decision_tree,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }
