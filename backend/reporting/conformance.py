"""Decision-tree conformance checks for rendered reports."""

from __future__ import annotations

from typing import Any

from data_trust import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text

from .mode_templates import decision_markdown_heading, get_report_template_profile, summary_markdown_heading


_REQUIRED_VISIBLE_MARKERS = (
    {"id": "data_trust", "label": "本報告資料可信度", "html": "本報告資料可信度", "markdown": "## 本報告資料可信度"},
    {"id": "execution_summary", "label": "執行邏輯與模型檢查", "html": "執行邏輯與模型檢查", "markdown": "## 執行邏輯與模型檢查"},
    {"id": "mode_template", "label": "報告模板與閱讀路徑", "html": "報告模板與閱讀路徑", "markdown": "## 報告模板與閱讀路徑"},
    {"id": "source_matrix", "label": "關鍵數據來源對照", "html": "關鍵數據來源對照", "markdown": "## 關鍵數據來源對照"},
    {"id": "source_audit", "label": "來源審計", "html": "來源審計", "markdown": "## 來源審計"},
)


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _as_list(value: Any) -> list:
    return safe_sequence_items(value)


def _text(value: Any, default: str = "") -> str:
    return safe_text(value).strip() or default


def _step(step_id: str, status: str, message: str, details: Any = None) -> dict:
    result = {"id": step_id, "status": status, "message": message}
    if details:
        result["details"] = details
    return result


def _missing_visible_markers(html: str, markdown: str, profile: dict[str, Any]) -> list[dict[str, str]]:
    missing = []
    html_text = _text(html)
    markdown_text = _text(markdown)
    for marker in _REQUIRED_VISIBLE_MARKERS:
        if marker["html"] not in html_text or marker["markdown"] not in markdown_text:
            missing.append({"id": marker["id"], "label": marker["label"]})
    summary_heading = _text(dict.get(profile, "summary_heading"), "一頁式摘要")
    if summary_heading not in html_text or summary_markdown_heading(profile) not in markdown_text:
        missing.append({"id": "tear_sheet", "label": summary_heading})
    decision_heading = _text(dict.get(profile, "decision_heading"), "最終投資建議")
    if decision_heading not in html_text or decision_markdown_heading(profile) not in markdown_text:
        missing.append({"id": "decision", "label": decision_heading})
    discipline_heading = _text(dict.get(profile, "discipline_heading"))
    if discipline_heading and (discipline_heading not in html_text or f"## {discipline_heading}" not in markdown_text):
        missing.append({"id": "decision_discipline", "label": discipline_heading})
    return missing


def _append_issue(target: list[dict], step: dict) -> None:
    target.append({"id": step["id"], "message": step["message"], "details": dict.get(step, "details")})


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
    decision_tree: list[dict] = []
    blocking_issues: list[dict] = []
    warnings: list[dict] = []

    lint_status = _text(dict.get(report_lint, "status"), "not_recorded")
    lint_blocking = _as_list(dict.get(report_lint, "blocking_issues"))
    lint_warnings = _as_list(dict.get(report_lint, "warnings"))
    if lint_status == "blocked" or lint_blocking:
        step = _step("report_lint", "blocked", "報告 lint 發現阻斷問題。", lint_blocking)
        _append_issue(blocking_issues, step)
    elif lint_status == "warning" or lint_warnings:
        step = _step("report_lint", "warning", "報告 lint 有警示。", lint_warnings)
        _append_issue(warnings, step)
    else:
        step = _step("report_lint", "passed", "報告 lint 通過。")
    decision_tree.append(step)

    missing_markers = _missing_visible_markers(html, markdown, profile)
    if missing_markers:
        step = _step("required_visibility", "blocked", "報告缺少必要可見段落。", missing_markers)
        _append_issue(blocking_issues, step)
    else:
        step = _step("required_visibility", "passed", "必要段落已在 HTML 與 Markdown 顯示。")
    decision_tree.append(step)

    final_audit = _as_dict(dict.get(context, "final_audit"))
    final_status = _text(dict.get(final_audit, "status"), "passed")
    critical = _as_list(dict.get(final_audit, "critical"))
    audit_warnings = _as_list(dict.get(final_audit, "warnings"))
    if final_status in {"blocked", "failed", "rejected"} or critical:
        step = _step("final_audit", "blocked", "最終稽核存在 critical 問題。", critical or final_status)
        _append_issue(blocking_issues, step)
    elif final_status != "passed" or audit_warnings:
        step = _step("final_audit", "warning", "最終稽核有警示需揭露。", audit_warnings or final_status)
        _append_issue(warnings, step)
    else:
        step = _step("final_audit", "passed", "最終稽核通過。")
    decision_tree.append(step)

    evidence_verdict = _text(dict.get(evidence_exit_gate, "verdict"), "not_recorded")
    if evidence_verdict == "rejected":
        step = _step("evidence_exit_gate", "blocked", "證據抽查拒絕報告數字。", evidence_exit_gate)
        _append_issue(blocking_issues, step)
    elif evidence_verdict != "approved":
        step = _step("evidence_exit_gate", "warning", "證據抽查未完全通過。", evidence_exit_gate)
        _append_issue(warnings, step)
    else:
        step = _step("evidence_exit_gate", "passed", "證據抽查通過。")
    decision_tree.append(step)

    content_status = _text(dict.get(content_credibility, "status"), "not_recorded")
    content_blocking = _as_list(dict.get(content_credibility, "blocking_issues"))
    content_warnings = _as_list(dict.get(content_credibility, "warnings"))
    if content_status == "blocked" or content_blocking:
        step = _step("content_credibility", "blocked", "內容可信度檢查發現阻斷矛盾。", content_blocking or content_credibility)
        _append_issue(blocking_issues, step)
    elif content_status == "warning" or content_warnings:
        step = _step("content_credibility", "warning", "內容可信度檢查有警示。", content_warnings or content_credibility)
        _append_issue(warnings, step)
    else:
        step = _step("content_credibility", "passed", "內容可信度檢查通過。")
    decision_tree.append(step)

    data_trust = normalize_data_trust(dict.get(snapshot, "data_trust") or dict.get(_as_dict(dict.get(context, "data")), "data_trust"))
    trust_status = _text(dict.get(data_trust, "status"), "unknown")
    if trust_status == "fresh":
        step = _step("data_trust", "passed", "資料可信度為 fresh。")
    else:
        label = trust_status_label(trust_status)
        step = _step("data_trust", "warning", f"資料可信度為 {label}（{trust_status}），報告需保留限制說明。", data_trust)
        _append_issue(warnings, step)
    decision_tree.append(step)

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
