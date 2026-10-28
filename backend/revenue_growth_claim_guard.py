"""Bind Yahoo's growth scalar to a local revenue claim and its stated period."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
import unicodedata

from financial_claim_context import NUMBER, is_actual_claim, section_heading, sentence_span
from financial_money_claims import other_financial_owner
from output_sanitizer import strip_generated_audit_sections

_PERCENT = re.compile(rf'(?P<number>{NUMBER})%')
_GROWTH = re.compile(r'營收(?:的)?(?:年增率?|成長率?|增長率?|季增率?|月增率?)|revenueGrowth', re.I)
_WRAPPED_VALUE = re.compile(
    rf'^(?P<label>[^\n%|]*(?:{_GROWTH.pattern})[:：])\n(?P<value>{NUMBER}%[。.]?)$',
    re.I | re.M,
)
_ANNUAL = re.compile(r'TTM|LTM|年度|全年|20\d{2}年(?!\d{1,2}月|第?[一二三四1-4]季|Q[1-4])', re.I)
_SHORT_PERIOD = re.compile(r'即期|近期|季度|本季|上季|第?[一二三四1-4]季|Q[1-4]|月度|本月|上月', re.I)
_RELABEL = re.compile(r'(?:可(?:直接)?|直接)?(?:視為|作為|等同(?:於)?|代表|稱為)')
_ERROR = re.compile(r'誤寫|誤稱|錯寫|錯稱|錯誤示例|錯誤範例|更正前|不採用|不可採用')
_ISSUE = (
    '成長率口徑紅線：Yahoo revenueGrowth 通常是近期/季度口徑，不可直接寫成 TTM 或年度營收年增率；'
    '請改用年度財報 YoY 或 TTM 相對最新年度 run-rate 檢查。'
)


def _percent_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip().removesuffix('%').replace('−', '-'))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def _table_claim_lines(clean):
    """Associate cells with their own metric column, retaining row scope."""
    headers = []
    for line in clean.splitlines():
        if not line.startswith('|') or not line.endswith('|'):
            headers = []
            yield line
            continue
        cells = line[1:-1].split('|')
        if all(re.fullmatch(r':?-+:?', cell) for cell in cells):
            continue
        if not _PERCENT.search(line):
            headers = cells
            continue
        shared = ''.join(cell for header, cell in zip(headers, cells)
                         if re.fullmatch(r'公司|標的|期間|年度|來源', header))
        for index, cell in enumerate(cells):
            if not _PERCENT.search(cell):
                continue
            header = headers[index] if len(headers) == len(cells) else ''
            if _GROWTH.search(header) or re.search(r'Yahoo.*成長率', header, re.I):
                yield shared + header + cell
            elif _GROWTH.search(cell):
                yield shared + cell
            else:
                preceding = [part for part in cells[:index]
                             if not _PERCENT.search(part) and _GROWTH.search(part)]
                if preceding:
                    yield shared + preceding[-1] + cell


def _adjacent_yahoo_growth_period(clean, percentages, index):
    """Carry a Yahoo period only across an adjacent, parallel growth pair."""
    if not index:
        return False
    previous, current = percentages[index - 1:index + 1]
    left, _ = sentence_span(clean, current.start(), current.end())
    if previous.start() < left:
        return False
    # Full matches exclude a changed issuer/source, contrast, an annual label,
    # intervening metrics, and a period borrowed from an earlier sentence.
    source = re.fullmatch(
        r'(?:依據[:：]?|根據)?Yahoo(?:即期|近期|季度)(?:獲利|盈餘|營收)'
        r'(?:年增率?|成長率?|增長率?)(?:顯示為|為|約為|約|[:：=])?',
        clean[left:previous.start()], re.I)
    parallel = re.fullmatch(
        r'[，,、](?:及|與|和|以及)?營收(?:年增率?|成長率?|增長率?)'
        r'(?:顯示為|為|約為|約|[:：=])?', clean[previous.end():current.start()])
    return bool(source and parallel)


def yahoo_growth_claim_issues(text: str, data: dict | None) -> list[str]:
    """Detect scalar relabeling, without certifying unrelated or equal digits."""
    if not isinstance(data, dict):
        return []
    source = _percent_value(data.get('yahoo_revenue_growth'))
    if source is None:
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or '')).replace('−', '-')
    clean = re.sub(r'[^\S\n]+|[*`]', '', clean)
    # Only a colon-terminated metric and an adjacent value-only line form one
    # wrapped claim. Blank lines and separate prose remain claim boundaries.
    clean = _WRAPPED_VALUE.sub(r'\g<label>\g<value>', clean)
    clean = '\n'.join(_table_claim_lines(clean))
    percentages = list(_PERCENT.finditer(clean))
    for index, match in enumerate(percentages):
        if _percent_value(match['number']) != source:
            continue
        left, right = sentence_span(clean, match.start(), match.end())
        # A preceding percentage owns its labels; a subsequent percentage cannot
        # donate a period or warning to this claim, even within one sentence.
        if index:
            left = max(left, percentages[index - 1].end())
        if index + 1 < len(percentages):
            right = min(right, percentages[index + 1].start())
        prefix = re.split(r'[，,|]|但是|然而|但', clean[left:match.start()])[-1]
        following = clean[match.end():right]
        suffix = re.split(r'[，,|]', following, maxsplit=1)[0]
        continuation = re.split(r'[，,|]', following, maxsplit=1)
        if len(continuation) == 2 and _RELABEL.match(continuation[1]):
            suffix += ',' + continuation[1]
        local = prefix + match.group() + suffix
        if not _GROWTH.search(local):
            continue
        # A metric after the value belongs here only when it explicitly renames
        # this value; otherwise it may introduce the next percentage.
        if not _GROWTH.search(prefix) and not _RELABEL.search(suffix):
            continue
        local_start, local_end = len(prefix), len(prefix) + len(match.group())
        heading = section_heading(clean, match.start())
        metrics = list(_GROWTH.finditer(prefix))
        owner = prefix[:metrics[-1].start()] if metrics else prefix
        if (not is_actual_claim(local, local_start, local_end)
                or _ERROR.search(local)
                or other_financial_owner(data, owner, heading)):
            continue
        period_scope = local
        if re.search(r'(?:不可|不能|不得|不應|勿)(?:直接)?(?:稱為|視為|作為|等同)', suffix):
            period_scope = prefix  # A denied renaming does not change this value's period.
        short_period = bool(_SHORT_PERIOD.search(period_scope))
        explicit_annual = bool(_ANNUAL.search(period_scope)) and (
            not short_period or bool(re.search(r'TTM|LTM|年度|全年', period_scope, re.I)))
        if not short_period and not explicit_annual:
            short_period = _adjacent_yahoo_growth_period(clean, percentages, index)
        # An explicit local period outranks a section heading; a generic claim
        # may inherit the heading, never another paragraph's caveat.
        if not explicit_annual and not short_period:
            explicit_annual = bool(_ANNUAL.search(heading))
            short_period = bool(_SHORT_PERIOD.search(heading))
        wrong_scope = explicit_annual or (not short_period and bool(
            re.search(r'營收年增率?|營收成長率高達', local)))
        if not wrong_scope:
            continue
        if (re.search(r'年度財報|年度財務', clean[left:match.start()])
                and not re.search(r'Yahoo|revenueGrowth', clean[left:match.end()], re.I)
                and not re.search(r'TTM|LTM|20\d{2}', local, re.I)
                and _percent_value(data.get('latest_annual_revenue_growth')) == source):
            # Equality alone is not evidence that the provider scalar was used.
            continue
        return [_ISSUE]
    return []
