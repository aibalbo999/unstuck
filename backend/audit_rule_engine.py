"""Config-driven hallucination guard rule evaluation."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from financial_claim_context import (
    NEGATION,
    NUMBER,
    VALUE_LINK,
    is_conditional_claim,
    revenue_growth_claims,
    section_heading,
    sentence_span,
)


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


def _has_high_revenue_growth(text: str) -> bool:
    return any(float(match.group("num")) >= 50 for match in revenue_growth_claims(text))


def _has_high_fcf_conversion(text: str) -> bool:
    pattern = rf"(?:FCF|自由現金流)(?:轉換率|/淨利){VALUE_LINK}(?:超過|>)?(?P<num>{NUMBER})%"
    return any(
        float(match.group("num")) >= 100 and not is_conditional_claim(text, match.start(), match.end())
        for match in re.finditer(pattern, text, re.IGNORECASE)
    )


def _has_priced_in_growth(text: str) -> bool:
    if _has_high_revenue_growth(text):
        return True
    for match in re.finditer(r"ForwardEPS隱含(?:營收需|營收必須|營收要)", text, re.IGNORECASE):
        _, right = sentence_span(text, match.start(), match.end())
        suffix = re.split(r"[，,|]", text[match.end():right], maxsplit=1)[0]
        if not re.search(rf"{NUMBER}%", suffix) and not is_conditional_claim(text, match.start(), match.end()):
            return True
    return False


def _has_accounting_goodwill(text: str) -> bool:
    for match in re.finditer("商譽", text):
        left, right = sentence_span(text, match.start(), match.end())
        clause = re.split(r"[，,|]", text[left:match.start()])[-1] + text[match.start():right]
        if is_conditional_claim(text, match.start(), match.end()):
            continue
        if re.search(r"(?:供應鏈|良好|業界|市場|企業)商譽", clause) and not re.search(
            r"商譽(?:帳面|金額|餘額|資產|為|達|\d)", clause
        ):
            continue
        if re.search(r"收購|併購|合併|認列|資產負債表|帳面|賬面|入帳|大量商譽|商譽(?:金額|餘額|資產)|商譽(?:為|達)?\d", clause):
            return True
    return False


def _is_bond_subject(text: str) -> bool:
    subjects = list(re.finditer(r"公債|國債|公司債|債券|美債|股息|股利|股票|配息", text))
    return bool(subjects and subjects[-1].group() in {"公債", "國債", "公司債", "債券", "美債"})


def _explicit_dividend_continuation(text: str, sentence_end: int, yield_pattern: str) -> str:
    if text[sentence_end:sentence_end + 2] == "\n\n":
        return ""
    start = sentence_end + 1
    if text[start:start + 1] == "\n":
        start += 1
    _, end = sentence_span(text, start, start)
    continuation = text[start:end]
    if not re.match(
        r"^(?:因此[，,]?(?:以(?:此|該)?高殖利率|(?:此|該)高殖利率|建議|值得|可以|具備|具有|買入)|(?:此|該)高殖利率)",
        continuation,
    ):
        return ""
    if (
        re.search(yield_pattern, continuation) or re.search(r"公債|國債|公司債|債券|美債", continuation)
        or NEGATION.search(continuation) or is_conditional_claim(text, start, start)
    ):
        return ""
    return continuation


def _has_high_dividend_buy_claim(text: str) -> bool:
    pattern = rf"殖利率{VALUE_LINK}(?P<num>{NUMBER})%"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        if float(match.group("num")) < 10 or is_conditional_claim(text, match.start(), match.end()):
            continue
        left, right = sentence_span(text, match.start(), match.end())
        prefix = re.split(r"[，,|]", text[left:match.start()])[-1]
        if _is_bond_subject(section_heading(text, match.start()) + prefix):
            continue
        sentence = text[left:right]
        yields = list(re.finditer(pattern, sentence, re.IGNORECASE))
        continuation = _explicit_dividend_continuation(text, right, pattern)
        if (
            continuation and yields[-1].start() + left == match.start()
            and not _is_bond_subject(text[match.end():right])
        ):
            sentence += "，" + continuation
        for endorsement in re.finditer(r"買入|吸引|低估|優質配息", sentence):
            preceding = [item for item in yields if item.start() < endorsement.start()]
            owner = preceding[-1] if preceding else yields[0]
            if owner.start() + left != match.start():
                continue
            clause_prefix = re.split(r"[，,|]|但是|然而|但", sentence[:endorsement.start()])[-1]
            if not NEGATION.search(clause_prefix) and not _is_bond_subject(clause_prefix):
                return True
    return False


SEMANTIC_CHECKS = {
    "high_revenue_growth": _has_high_revenue_growth,
    "high_fcf_conversion": _has_high_fcf_conversion,
    "priced_in_growth": _has_priced_in_growth,
    "accounting_goodwill": _has_accounting_goodwill,
    "high_dividend_buy_claim": _has_high_dividend_buy_claim,
}


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
        if not all(SEMANTIC_CHECKS[name](normalized_text) for name in rule.get("semantic_checks", [])):
            continue
        if any(str(term) in normalized_text for term in rule.get("not_any_substrings", []) or []):
            continue
        issues.append(str(rule.get("issue", "")).strip())

    return [issue for issue in issues if issue]
