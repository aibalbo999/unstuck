"""Decision-tree step builders for report conformance gates."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text

from .conformance_data_trust_step import build_data_trust_conformance_step
from .conformance_step_result import merge_step_result, step, step_result
from .text_tokens import is_missing_text_token


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _as_list(value: Any) -> list:
    return safe_sequence_items(value)


def _text(value: Any, default: str = "") -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return text or default


def _report_lint_step(report_lint: dict) -> dict:
    lint_status = _text(dict.get(report_lint, "status"), "not_recorded")
    lint_blocking = _as_list(dict.get(report_lint, "blocking_issues"))
    lint_warnings = _as_list(dict.get(report_lint, "warnings"))
    if lint_status == "blocked" or lint_blocking:
        return step_result(
            step("report_lint", "blocked", "報告 lint 發現阻斷問題。", lint_blocking),
            issue_kind="blocking",
        )
    if lint_status == "warning" or lint_warnings:
        return step_result(
            step("report_lint", "warning", "報告 lint 有警示。", lint_warnings),
            issue_kind="warning",
        )
    return step_result(step("report_lint", "passed", "報告 lint 通過。"))


def _final_audit_step(context: dict) -> dict:
    final_audit = _as_dict(dict.get(context, "final_audit"))
    final_status = _text(dict.get(final_audit, "status"), "passed")
    critical = _as_list(dict.get(final_audit, "critical"))
    audit_warnings = _as_list(dict.get(final_audit, "warnings"))
    if final_status in {"blocked", "failed", "rejected"} or critical:
        return step_result(
            step("final_audit", "blocked", "最終稽核存在 critical 問題。", critical or final_status),
            issue_kind="blocking",
        )
    if final_status != "passed" or audit_warnings:
        return step_result(
            step("final_audit", "warning", "最終稽核有警示需揭露。", audit_warnings or final_status),
            issue_kind="warning",
        )
    return step_result(step("final_audit", "passed", "最終稽核通過。"))


def _evidence_exit_gate_step(evidence_exit_gate: dict) -> dict:
    evidence_verdict = _text(dict.get(evidence_exit_gate, "verdict"), "not_recorded")
    evidence_details = {**evidence_exit_gate, "verdict": evidence_verdict}
    if evidence_verdict == "rejected":
        return step_result(
            step("evidence_exit_gate", "blocked", "證據抽查拒絕報告數字。", evidence_details),
            issue_kind="blocking",
        )
    if evidence_verdict != "approved":
        return step_result(
            step("evidence_exit_gate", "warning", "證據抽查未完全通過。", evidence_details),
            issue_kind="warning",
        )
    return step_result(step("evidence_exit_gate", "passed", "證據抽查通過。"))


def _content_credibility_step(content_credibility: dict) -> dict:
    content_status = _text(dict.get(content_credibility, "status"), "not_recorded")
    content_blocking = _as_list(dict.get(content_credibility, "blocking_issues"))
    content_warnings = _as_list(dict.get(content_credibility, "warnings"))
    if content_status == "blocked" or content_blocking:
        return step_result(
            step("content_credibility", "blocked", "內容可信度檢查發現阻斷矛盾。", content_blocking or content_credibility),
            issue_kind="blocking",
        )
    if content_status == "warning" or content_warnings:
        return step_result(
            step("content_credibility", "warning", "內容可信度檢查有警示。", content_warnings or content_credibility),
            issue_kind="warning",
        )
    return step_result(step("content_credibility", "passed", "內容可信度檢查通過。"))


def build_conformance_gate_steps(
    *,
    context: dict,
    snapshot: dict,
    report_lint: dict,
    evidence_exit_gate: dict,
    content_credibility: dict,
) -> dict:
    """Build non-visibility decision-tree steps and issue buckets for report conformance."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    report_lint = _as_dict(report_lint)
    evidence_exit_gate = _as_dict(evidence_exit_gate)
    content_credibility = _as_dict(content_credibility)
    result = {"decision_tree": [], "blocking_issues": [], "warnings": []}
    for step_result in (
        _report_lint_step(report_lint),
        _final_audit_step(context),
        _evidence_exit_gate_step(evidence_exit_gate),
        _content_credibility_step(content_credibility),
        build_data_trust_conformance_step(context=context, snapshot=snapshot),
    ):
        merge_step_result(result, step_result)
    return result
