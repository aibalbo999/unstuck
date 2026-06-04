"""Config-driven hallucination guard rule evaluation."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


RULES_FILE = Path(__file__).resolve().parent / "prompts" / "audit_rules.json"


@lru_cache(maxsize=1)
def load_audit_rules(rules_file: str | None = None) -> list[dict]:
    path = Path(rules_file) if rules_file else RULES_FILE
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rules = payload.get("rules", []) if isinstance(payload, dict) else []
    return [rule for rule in rules if isinstance(rule, dict)]


def _agent_matches(rule: dict, agent_num: int) -> bool:
    agents = rule.get("agents")
    if not agents:
        return True
    return agent_num in set(int(agent) for agent in agents)


def _contains_all(text: str, terms: list[str]) -> bool:
    return all(str(term) in text for term in terms or [])


def _matches_all_regex(text: str, patterns: list[str]) -> bool:
    return all(re.search(str(pattern), text, flags=re.IGNORECASE) for pattern in patterns or [])


def _matches_any_group(text: str, groups: list[list[str]]) -> bool:
    return all(any(str(term) in text for term in group) for group in groups or [])


def _matches_any_regex_group(text: str, groups: list[list[str]]) -> bool:
    return all(
        any(re.search(str(pattern), text, flags=re.IGNORECASE) for pattern in group)
        for group in groups or []
    )


def evaluate_configured_audit_rules(
    agent_num: int,
    normalized_text: str,
    *,
    has_data_quality_caveat: bool,
) -> list[str]:
    """Return audit issues triggered by JSON-configured text rules."""
    issues: list[str] = []
    for rule in load_audit_rules():
        if not _agent_matches(rule, agent_num):
            continue
        if rule.get("requires_no_data_quality_caveat") and has_data_quality_caveat:
            continue
        if not _contains_all(normalized_text, rule.get("all_substrings", [])):
            continue
        if not _matches_all_regex(normalized_text, rule.get("all_regex", [])):
            continue
        if not _matches_any_group(normalized_text, rule.get("any_substring_groups", [])):
            continue
        if not _matches_any_regex_group(normalized_text, rule.get("any_regex_groups", [])):
            continue
        if any(str(term) in normalized_text for term in rule.get("not_any_substrings", []) or []):
            continue
        issues.append(str(rule.get("issue", "")).strip())

    return [issue for issue in issues if issue]
