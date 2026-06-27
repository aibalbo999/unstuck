"""Critical final-decision lint rules used before repair closes."""

from __future__ import annotations

import re

from reporting.lint import get_critical_lint_rules


def critical_lint_issues_for_pipeline(pipeline_id: str, output: str) -> list[str]:
    if pipeline_id == "v3":
        rules = [
            {"id": "missing_short_trigger", "pattern": r"做空觸發|short.*trigger|空單進場", "label": "做空觸發條件"},
        ]
    elif pipeline_id == "v4":
        rules = [
            {"id": "missing_entry_zone", "pattern": r"entry.*zone|進場區間|entry_zone", "label": "進場區間"},
        ]
    else:
        rules = get_critical_lint_rules()

    issues = []
    for rule in rules:
        if not re.search(rule["pattern"], output or "", re.IGNORECASE):
            issues.append(f"最終決策 Agent 輸出缺少「{rule['label']}」，請補齊。")
    return issues
