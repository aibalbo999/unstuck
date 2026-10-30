"""Config-driven hallucination guard rule evaluation."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from financial_claim_context import (
    NEGATION,
    NUMBER,
    SENTENCE_BREAK,
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


_PB_METRIC = re.compile(r"股價淨值比(?:[（(]P/B[）)])?|P/B(?:[（(]股價淨值比[）)])?", re.IGNORECASE)
_EQUITY_RISK = re.compile(
    r"負淨值|(?:每股淨值|股東權益|權益總額|淨值)(?:為|是|呈|已|僅|=|:|：)*"
    r"(?:負(?:數|值)?|極低|非常低|接近零|[-−]\d+(?:\.\d+)?(?:億|萬)?元)"
)
_PB_SCOPE_BREAK = re.compile(
    SENTENCE_BREAK.pattern + r"|[，,](?=(?:而|但)?(?:[A-Za-z\u4e00-\u9fff]{1,12}公司|同業|"
    r"今年|去年|本季|上季|20\d{2}年))"
)


def _pb_risk_evidence(text: str) -> bool:
    numeric_pb = re.compile(rf"(?:{_PB_METRIC.pattern}){VALUE_LINK}(?P<num>{NUMBER})", re.IGNORECASE)
    for match in [*_EQUITY_RISK.finditer(text), *numeric_pb.finditer(text)]:
        prefix = re.split(r"[，,|]|但是|然而|但", text[:match.start()])[-1]
        if NEGATION.search(prefix) or re.match(r"(?:問題|狀態)?已(?:消除|解除|轉正)", text[match.end():]):
            continue
        if match.re is _EQUITY_RISK or float(match['num']) < 0:
            return True
    return False


def _pb_scope_spans(text: str):
    start = 0
    for boundary in _PB_SCOPE_BREAK.finditer(text):
        if text[start:boundary.start()].strip():
            yield start, boundary.start()
        start = boundary.end()
    if text[start:].strip():
        yield start, len(text)


def _has_negative_equity_pb_bargain(text: str) -> bool:
    """Bind a bargain assertion to its P/B and local negative-equity evidence."""
    text = re.sub(r"[*`]", "", text).replace('−', '-')
    previous = ""
    previous_end = 0
    for left, right in _pb_scope_spans(text):
        if re.search(r"\n[^\S\n]*\n", text[previous_end:left]):
            previous = ""
        sentence = text[left:right].strip()
        metrics = list(_PB_METRIC.finditer(sentence))
        for claim in re.finditer(r"低估|便宜|折讓|吸引|買入", sentence):
            prefix = re.split(r"[，,|]|但是|然而|但", sentence[:claim.start()])[-1]
            if NEGATION.search(prefix) or re.search(r"是否|待確認|待查核", prefix):
                continue
            owners = [metric for metric in metrics if metric.end() <= claim.start()]
            if not owners and metrics and re.fullmatch(
                r"[，,]?(?:原因是|因為|因|由於)", sentence[claim.end():metrics[0].start()]
            ):
                owners = metrics[:1]
            if not owners:
                continue
            owner = owners[-1]
            # A second P/B starts a new valuation claim, not a global risk flag.
            start = 0
            if len(owners) > 1:
                boundary = max(sentence.rfind(mark, owners[-2].end(), owner.start()) for mark in '，,|')
                start = boundary + 1 if boundary >= 0 else owner.start()
            end = next((metric.start() for metric in metrics if metric.start() > owner.start()), len(sentence))
            evidence = sentence[start:end]
            if start == 0 and re.match(
                r"^(?:因此|所以|故)?(?:其|該公司|該|此)(?:的)?(?:低)?(?:P/B|股價淨值比)", sentence, re.IGNORECASE
            ):
                evidence = previous + '，' + evidence
            if _pb_risk_evidence(evidence):
                return True
        previous = sentence
        previous_end = right
    return False


_DUPONT_METRICS = r'(?:ROE|ROA|淨利率)'
_DUPONT_BALANCE_FACTORS = r'(?:資產[周週]轉率?|權益乘數)'
_DUPONT_ANNUAL = r'(?:20\d{2}年?(?:年度)?|最新年度|上年度|本年度|年度|全年)'


def _dupont_calculation_scopes(text: str):
    """A named calculation owns its contiguous prose/table, never the report."""
    lines = []; heading = ''; in_code = False; list_calculation = False
    for raw in text.splitlines():
        line = re.sub(r'[*`]', '', raw).strip()
        if raw.strip().startswith('```'):
            if lines:
                yield heading + '\n' + '\n'.join(lines)
            lines = []; list_calculation = False; in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith('#'):
            if lines:
                yield heading + '\n' + '\n'.join(lines)
            lines = []; list_calculation = False
            heading = line if re.search(r'杜邦|DuPont', line, re.I) else ''
            continue
        if not line:
            # Within a named DuPont section, successive prose and table rows
            # still describe that calculation until the next section heading.
            if lines and not heading:
                yield '\n'.join(lines)
                lines = []; list_calculation = False
            continue
        if re.match(r'^[-+]\s*', line) and lines and not heading:
            if not list_calculation:
                yield '\n'.join(lines)
                lines = []
        if not lines:
            list_calculation = bool(re.search(r'(?:杜邦|DuPont).{0,12}[:：]$', line, re.I))
        lines.append(line)
    if lines:
        yield heading + '\n' + '\n'.join(lines)


def _active_dupont_scope(scope: str) -> str:
    """Discard only local prohibitions/comparison-only claims, never caveats."""
    active = []
    for sentence in re.split(r'[。；;！？!?]|(?<!\d)\.(?!\d)|但是|然而|[，,]但', scope):
        sentence = sentence.strip()
        if not sentence:
            continue
        clean = re.sub(r'^[-+]\s*', '', sentence)
        clean = re.sub(r'^(?:杜邦分析紅線|注意|警示)[:：]', '', clean)
        if re.match(r'^(?:不可|不得|不應|禁止|避免)(?:把|將|使用|採用|混用|跨期|拼接)', clean):
            continue
        if re.match(r'^(?:若|如果|假如)', clean) and re.search(r'不得|不可|不應|避免', clean):
            continue
        comparison = re.search(r'僅供對照|僅作(?:資料品質)?警示|僅列為資料品質警示|不(?:進行)?跨期拼接', clean)
        # A real formula or affirmative mixing cannot borrow a warning later
        # in this sentence or anywhere else in the report.
        calculation = re.sub(r'不(?:進行)?跨期拼接|不可拼接|不得拼接', '', clean)
        if comparison and not re.search(r'使用|採用|拼接|相乘|共同計算|[=×]', calculation):
            continue
        active.append(sentence)
    return '。'.join(active)


def _mixed_dupont_table_columns(scope: str) -> bool:
    """Bind a transposed period row to its own table's metric columns."""
    headers = []
    for line in scope.splitlines():
        if not line.strip().startswith('|'):
            headers = []
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if not cells or all(re.fullmatch(r':?-{2,}:?', cell) for cell in cells):
            continue
        if any(re.fullmatch(_DUPONT_METRICS, cell, re.I) for cell in cells):
            headers = cells
            continue
        if not headers or len(cells) != len(headers) or not re.fullmatch(r'期間|年度|口徑|period', cells[0], re.I):
            continue
        # A complete annual row and a separate complete TTM row are distinct
        # calculations. Never union period evidence across rows or tables.
        ttm_metric = any(re.fullmatch(_DUPONT_METRICS, metric, re.I)
                         and re.fullmatch(r'TTM|LTM', period, re.I)
                         for metric, period in zip(headers, cells))
        annual_factor = any(re.fullmatch(_DUPONT_BALANCE_FACTORS, metric)
                            and re.fullmatch(_DUPONT_ANNUAL, period)
                            for metric, period in zip(headers, cells))
        if ttm_metric and annual_factor:
            return True
    return False


def _has_mixed_ttm_dupont(text: str) -> bool:
    for raw_scope in _dupont_calculation_scopes(text):
        scope = _active_dupont_scope(raw_scope)
        if not re.search(r'杜邦|DuPont', raw_scope, re.I) or not re.search(_DUPONT_BALANCE_FACTORS, scope):
            continue
        if _mixed_dupont_table_columns(scope):
            return True
        # TTM on an unrelated cash-flow/revenue claim is not a DuPont period.
        ttm_metric = any(re.search(r'TTM|LTM', clause, re.I) and re.search(_DUPONT_METRICS, clause, re.I)
                         for clause in re.split(r'[。；;，,\n]', scope))
        if not ttm_metric:
            # A TTM calculation heading binds the following rows, including
            # Markdown tables whose period and metric are in distinct cells.
            ttm_metric = bool(re.search(r'(?:TTM|LTM)(?:杜邦|DuPont)|(?:杜邦|DuPont)(?:分析|計算|公式)?[:：]?(?:TTM|LTM)', scope, re.I)
                              and re.search(_DUPONT_METRICS, scope, re.I))
        if not ttm_metric:
            continue
        annual_factor = bool(re.search(_DUPONT_ANNUAL + r'[^。；;\n]{0,40}' + _DUPONT_BALANCE_FACTORS, scope, re.I)
                             or re.search(_DUPONT_BALANCE_FACTORS + r'[^。；;\n]{0,40}' + _DUPONT_ANNUAL, scope, re.I)
                             or re.search(_DUPONT_ANNUAL + r'(?:同期間)?(?:杜邦|DuPont)', scope, re.I))
        explicit_mixing = bool(re.search(r'跨期拼接|不同期間.{0,12}(?:拼接|相乘)|(?:拼接|相乘).{0,12}不同期間', scope))
        unexplained_ttm_gap = bool(re.search(r'(?:TTM|LTM)(?:杜邦|DuPont)', scope, re.I)
            and re.search(r'資產[周週]轉', scope) and '權益乘數' in scope
            and re.search(r'(?:ROE|ROA)(?:數值|的)?(?:差距|落差|不一致|偏差)|口徑(?:差距|不一致|偏差)', scope, re.I))
        if annual_factor or explicit_mixing or unexplained_ttm_gap:
            return True
    return False


SEMANTIC_CHECKS = {
    "mixed_ttm_dupont": _has_mixed_ttm_dupont,
    "high_revenue_growth": _has_high_revenue_growth,
    "high_fcf_conversion": _has_high_fcf_conversion,
    "priced_in_growth": _has_priced_in_growth,
    "accounting_goodwill": _has_accounting_goodwill,
    "high_dividend_buy_claim": _has_high_dividend_buy_claim,
    "negative_equity_pb_bargain": _has_negative_equity_pb_bargain,
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
