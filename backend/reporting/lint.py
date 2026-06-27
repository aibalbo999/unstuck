"""Pre-save lint for rendered report artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


class ReportLintError(RuntimeError):
    def __init__(self, result: dict):
        self.result = result
        issues = result.get("blocking_issues", [])
        message = "Report pre-save lint failed"
        if issues:
            message = f"{message}: {issues[0].get('label', 'unknown issue')}"
        super().__init__(message)


@dataclass(frozen=True)
class _Rule:
    label: str
    pattern: re.Pattern


BLOCKING_RULES = (
    _Rule("prompt_role_leak", re.compile(r"Senior Financial Media Host|Senior Analyst at Goldman Sachs|Chief Economist and Industry Strategist|Forensic Accountant|Financial Risk Specialist", re.I)),
    _Rule("debate_role_leak", re.compile(r"\b(?:Bull|Bear)\s*\(\s*Dr\.|Dr\.\s*(?:Chen|Li)\s*:", re.I)),
    _Rule("structured_json_key_leak", re.compile(r"\b(?:peer_reasoning|dcf_reasoning|scenario_reasoning|analysis_markdown|moat_scores|price_targets|reasoning_steps)\b")),
    _Rule("agent_execution_failure", re.compile(r"\[Agent\s+\d+\s+執行失敗|所有模型/Key 不可用|RESOURCE_EXHAUSTED|Too Many Requests|HTTP\s*429", re.I)),
    _Rule("repair_process_leak", re.compile(r"AI 修復失敗|AI 修復不可用|最終稽核修復階段|前次退件反思摘要|本修復版|保守修復版")),
    _Rule("raw_prompt_instruction", re.compile(r"Valid parseable JSON only|No markdown code fences|No extra text outside JSON|Specific JSON schema|No roleplay meta-talk", re.I)),
)

STRUCTURED_JSON_KEY_RE = re.compile(
    r"\b(?:peer_reasoning|dcf_reasoning|scenario_reasoning|analysis_markdown|moat_scores|price_targets|reasoning_steps)\b"
)

WARNING_RULES = (
    _Rule("audit_attention_notice", re.compile(r"系統異常提醒|仍需注意的異常|缺少目標價|缺少最終投資建議")),
)


def get_critical_lint_rules() -> list[dict]:
    return [
        {"id": "missing_recommendation", "pattern": r"投資建議|買進|賣出|持有|中立", "label": "投資建議段落"},
        {"id": "missing_target_price", "pattern": r"目標價|target.{0,10}price", "label": "目標價"},
    ]


def _scan(text: str, rules: Iterable[_Rule], artifact: str) -> list[dict]:
    issues = []
    for rule in rules:
        match = rule.pattern.search(text or "")
        if not match:
            continue
        snippet = re.sub(r"\s+", " ", match.group(0)).strip()[:120]
        issues.append({"artifact": artifact, "label": rule.label, "snippet": snippet})
    return issues


def lint_report_artifacts(html: str, markdown: str) -> dict:
    blocking = []
    warnings = []
    for artifact, text in (("html", html), ("markdown", markdown)):
        blocking.extend(_scan(text, BLOCKING_RULES, artifact))
        warnings.extend(_scan(text, WARNING_RULES, artifact))

    status = "passed"
    if warnings:
        status = "warning"
    if blocking:
        status = "blocked"
    return {
        "status": status,
        "blocking_issues": blocking,
        "warnings": warnings,
        "checked_artifacts": ["html", "markdown"],
    }


def _structured_key_replacement(match: re.Match) -> str:
    return {
        "analysis_markdown": "分析正文",
        "reasoning_steps": "推論摘要",
        "moat_scores": "護城河評分",
        "price_targets": "目標價",
        "dcf_reasoning": "DCF 推論",
        "peer_reasoning": "同業比較推論",
        "scenario_reasoning": "情境推論",
    }.get(match.group(0), "內部欄位")


def scrub_structured_json_key_leaks(text: str) -> str:
    """Remove internal structured-output key names from rendered artifacts."""
    if not text:
        return ""
    return STRUCTURED_JSON_KEY_RE.sub(_structured_key_replacement, text)


def assert_report_lint_passed(html: str, markdown: str) -> dict:
    result = lint_report_artifacts(html, markdown)
    if result["blocking_issues"]:
        raise ReportLintError(result)
    return result
