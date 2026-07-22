"""Repair item builders for report quality gates."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text, safe_text_list

GateRule = tuple[str, int, str, str, str, str, list[str], bool]


CONTENT_CREDIBILITY_RULES: dict[str, GateRule] = {
    "blocked": ("blocked", 1000, "manual_review", "人工審核", "內容可信度未通過", "報告建議、目標價或資料限制互相矛盾。", ["content_credibility_blocked"], True),
    "warning": ("warning", 780, "manual_review", "人工審核", "內容可信度需確認", "報告內容可信度有警示，採用前需人工確認。", ["content_credibility_warning"], False),
}

REPORT_CONFORMANCE_RULES: dict[str, GateRule] = {
    "blocked": ("blocked", 960, "manual_review", "人工審核", "報告符合性未通過", "報告未符合輸出契約。", ["report_conformance_blocked"], True),
    "warning": ("warning", 740, "manual_review", "人工審核", "報告符合性需確認", "報告符合主要契約，但仍需人工確認。", ["report_conformance_warning"], False),
}

EVIDENCE_EXIT_GATE_RULES: dict[str, GateRule] = {
    "rejected": ("blocked", 940, "manual_review", "人工審核", "證據抽查未通過", "報告數字未能對上資料快照。", ["evidence_exit_gate_rejected"], True),
    "caution": ("warning", 720, "manual_review", "人工審核", "數字證據需核對", "部分報告數字需人工確認。", ["evidence_exit_gate_caution"], False),
}


def content_credibility_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    return _gate_repair_item(report, "content_credibility", "status", CONTENT_CREDIBILITY_RULES)


def report_conformance_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    return _gate_repair_item(report, "report_conformance", "status", REPORT_CONFORMANCE_RULES)


def evidence_exit_gate_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    return _gate_repair_item(report, "evidence_exit_gate", "verdict", EVIDENCE_EXIT_GATE_RULES)


def data_trust_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    trust = _dict(_field(report, "data_trust"))
    status = _status(_field(trust, "status"))
    codes = _reason_codes(trust)
    if status == "error" or any(code.startswith("source_error:") for code in codes):
        return _item(
            severity="blocked",
            priority=860,
            action="manual_review",
            label="查看報告",
            title="資料來源異常",
            detail="資料來源錯誤，採用或重跑前需先確認來源審計。",
            reason_codes=codes or ["data_trust_error"],
            blocks_auto_rerun=True,
        )
    if status == "stale" or _has_stale_source(trust, codes):
        return _item(
            severity="warning",
            priority=620,
            action="refresh_data_snapshot",
            label="刷新資料",
            title="資料快照過期",
            detail="先刷新資料快照，再判斷是否需要完整重跑。",
            reason_codes=codes or ["data_trust_stale"],
        )
    return None


def decision_freshness_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    freshness = _dict(_field(report, "decision_freshness"))
    if not (
        _safe_bool(_field(freshness, "requires_rerun"))
        or _safe_bool(_field(report, "requires_rerun"))
        or _safe_bool(_field(report, "analysis_text_stale"))
    ):
        return None
    detail = _first_text(
        _field(freshness, "requires_rerun_reason"),
        _field(report, "analysis_text_stale_message"),
        _field(report, "requires_rerun_reason"),
        fallback="資料快照與結論不同步，舊 Markdown 不應視為最新判斷。",
    )
    return _item(
        severity="warning",
        priority=700,
        action="rerun_analysis",
        label="完整重跑",
        title="結論需完整重跑",
        detail=detail,
        reason_codes=["decision_freshness_needs_rerun"],
    )


def _gate_repair_item(
    report: dict[str, Any],
    gate_key: str,
    status_key: str,
    rules: dict[str, GateRule],
) -> dict[str, Any] | None:
    gate = _dict(_field(report, gate_key))
    rule = rules.get(_status(_field(gate, status_key)))
    if rule is None:
        return None
    severity, priority, action, label, title, fallback, reason_codes, blocks_auto_rerun = rule
    return _item(
        severity=severity,
        priority=priority,
        action=action,
        label=label,
        title=title,
        detail=_summary(gate, fallback),
        reason_codes=reason_codes,
        blocks_auto_rerun=blocks_auto_rerun,
    )


def _item(
    *,
    severity: str,
    priority: int,
    action: str,
    label: str,
    title: str,
    detail: str,
    reason_codes: list[str],
    blocks_auto_rerun: bool = False,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "priority_score": priority,
        "recommended_action": action,
        "action_label": label,
        "title": title,
        "detail": detail,
        "reason_codes": reason_codes,
        "blocks_auto_rerun": blocks_auto_rerun,
    }


def _dict(value: Any) -> dict[str, Any]:
    return safe_mapping_dict(value) or {}


def _field(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    return dict.get(mapping, key, default)


def _status(value: Any) -> str:
    return safe_text(value).strip().lower()


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return False


def _summary(payload: dict[str, Any], fallback: str) -> str:
    summary = safe_text(_field(payload, "summary")).strip()
    if summary:
        return summary
    message = safe_text(_field(payload, "message")).strip()
    if message:
        return message
    return fallback


def _first_text(*values: Any, fallback: str) -> str:
    for value in values:
        text = safe_text(value).strip()
        if text:
            return text
    return fallback


def _reason_codes(trust: dict[str, Any]) -> list[str]:
    return safe_text_list(_field(trust, "reason_codes"))


def _has_stale_source(trust: dict[str, Any], codes: list[str]) -> bool:
    return bool(safe_text_list(_field(trust, "stale_sources"))) or any(code.startswith("source_stale:") for code in codes)
