"""Reject an observed D/E value relabeled as debt/assets, without deriving a ratio."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import re
import unicodedata

from financial_claim_context import is_actual_claim, section_heading, sentence_span
from output_sanitizer import strip_generated_audit_sections

_DEBT_ASSETS = re.compile(
    r'(?P<label>負債比率|負債(?:佔|占|對|/)資產(?:比率|比)?)'
    r'(?:高達|達到|約為|為|約|達|維持在|目前|最新|[:：=|])*'
    r'(?P<number>[+-]?\d+(?:\.\d+)?)%')
_OTHER_PERIOD = re.compile(r'20\d{2}|去年|前年|第?[一二三四1-4]季|Q[1-4]|[上下]半年', re.I)
_ERROR = re.compile(r'誤寫|誤稱|錯寫|錯稱|錯誤示例|錯誤範例|更正前|不採用|不可採用')
_PEER = re.compile(r'同業|同儕|競爭(?:者|對手)|peer|competitor', re.I)
_NET_MARGIN_LABEL = r'(?:稅後)?淨利率'
_NET_MARGIN = re.compile(
    rf'{_NET_MARGIN_LABEL}(?:\([^\d%\n]{{1,12}}\))?'
    r'(?:高達|達到|約為|為|約|達|目前|最新|僅|是|[:：=|])*'
    r'(?P<number>[+-]?\d+(?:\.\d+)?)%')


def debt_ratio_claim_issues(text: str, data: dict | None) -> list[str]:
    """Only identify reuse of the input D/E scalar, not certify other D/A claims.

    This scalar has no verified balance-sheet date. Explicit historical periods
    cannot be compared, and total debt is never substituted for total liabilities.
    """
    if not isinstance(data, dict):
        return []
    source = data.get('debt_to_equity')
    if source is None or isinstance(source, bool):
        return []
    try:
        source = float(str(source).strip().removesuffix('%'))
    except (TypeError, ValueError, OverflowError):
        return []
    if not math.isfinite(source):
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or ''))
    clean = re.sub(r'[^\S\n]+|[*`]', '', clean).replace('−', '-')
    issues = []
    for match in _DEBT_ASSETS.finditer(clean):
        left, right = sentence_span(clean, match.start(), match.end())
        local = clean[left:right]
        heading = section_heading(clean, match.start())
        if (not is_actual_claim(clean, match.start(), match.end())
                or _OTHER_PERIOD.search(local + heading)
                or _ERROR.search(local) or _PEER.search(local + heading)):
            continue
        number = match['number']
        precision = len(number.partition('.')[2])
        try:
            rounded = Decimal(str(source)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
            if rounded != Decimal(number):
                continue
        except InvalidOperation:
            continue
        issues.append(
            f'負債比率口徑紅線：原文「{match.group()}」沿用了 data.debt_to_equity={source:g}%；'
            '此來源是負債／權益（D/E），不是負債／資產（D/A），請使用「負債權益比」。'
            '未提供同期間總負債與總資產時，負債比率維持尚未確認，不得借用舊年度權益乘數或自行換算。')
    return list(dict.fromkeys(issues))


def _margin_table_lines(clean):
    headers = []
    for line in clean.splitlines():
        yield line
        if not line.startswith('|') or not line.endswith('|'):
            headers = []
            continue
        cells = line[1:-1].split('|')
        if len(cells) == 2 and re.fullmatch(_NET_MARGIN_LABEL, cells[0]):
            yield ''.join(cells)
        if any(re.fullmatch(rf'(?:TTM|LTM)?{_NET_MARGIN_LABEL}', cell, re.I) for cell in cells):
            headers = cells
        elif headers and len(cells) == len(headers):
            for index, label in enumerate(headers):
                if re.fullmatch(rf'(?:TTM|LTM)?{_NET_MARGIN_LABEL}', label, re.I):
                    # Keep the row owner/period; never borrow another column's percentage.
                    yield ''.join(cells[:index]) + label + cells[index]


def provider_margin_claim_issues(text: str, data: dict | None) -> list[str]:
    """Reject reuse of a conflicting provider margin, not unrelated equal digits."""
    if not isinstance(data, dict):
        return []
    values = []
    for key in ('profit_margin_provider', 'profit_margin'):
        value = data.get(key)
        if value is None or isinstance(value, bool):
            return []
        try:
            number = float(str(value).strip().removesuffix('%'))
        except (TypeError, ValueError, OverflowError):
            return []
        if not math.isfinite(number):
            return []
        values.append(number)
    provider, calibrated = values
    if math.isclose(provider, calibrated, abs_tol=1e-9):
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or ''))
    clean = re.sub(r'[^\S\n]+|[*`]', '', clean).replace('−', '-')
    clean = '\n'.join(_margin_table_lines(clean))
    issues = []
    for match in _NET_MARGIN.finditer(clean):
        if not math.isclose(float(match['number']), provider, rel_tol=0, abs_tol=1e-9):
            continue
        left, right = sentence_span(clean, match.start(), match.end())
        prefix = re.split(r'[，,|]', clean[left:match.start()])[-1]
        suffix = re.split(r'[，,|]', clean[match.end():right], maxsplit=1)[0]
        local = prefix + match.group() + suffix
        heading = section_heading(clean, match.start())
        source_warning = (
            re.search(r'Yahoo原始|資料源對照|口徑互斥', local, re.I)
            and (re.search(r'僅供對照|僅列為警示|資料品質警示|不採用|不可採用', local)
                 or re.match(r'[，,](?:此值|該值|原始值)?不採用', clean[match.end():right])))
        if (not is_actual_claim(clean, match.start(), match.end())
                or _ERROR.search(local) or _PEER.search(prefix)
                or source_warning
                or (_OTHER_PERIOD.search(prefix + heading) and not re.search(r'TTM|LTM', prefix, re.I))):
            continue
        issues.append(
            f'淨利率口徑紅線：原文「{match.group()}」沿用了 Yahoo 原始 profitMargins={provider:g}%，'
            f'與校準後淨利率 {calibrated:g}% 口徑互斥；正式分析必須採用校準後淨利率，'
            '原始值只能作為資料品質警示，不把其他期間、同業、評分或未來條件當成本次淨利率。')
    return list(dict.fromkeys(issues))
