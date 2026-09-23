"""Bounded actual-money checks against typed annual histories and raw TTM FCF.

This is not a general numeric fact checker. Unknown scope/currency/source stays
unverified; scenario estimates and other financial periods are not compared.
"""
from __future__ import annotations

import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from financial_claim_context import sentence_span, section_heading
from output_sanitizer import strip_generated_audit_sections

_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_AMOUNT = re.compile(
    r"(?P<metric>自由現金流|FCF|營業收入|營收|稅後淨利|淨利)"
    r"(?P<link>(?:(?!自由現金流|FCF|營業收入|營收|稅後淨利|淨利)[^\d。；;，,\n]){0,35}?)"
    rf"(?P<number>{_NUMBER})\s*"
    r"(?P<unit>十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)"
    r"(?![A-Za-z])", re.I,
)
_PERIOD = re.compile(
    r"20\d{2}(?:[-/.]\d{1,2}(?:[-/.]\d{1,2})?)?\s*年?(?:\s*(?:\d{1,2}\s*月|Q[1-4]|第?[一二三四1-4]\s*季|[上下]半年))?"
    r"|\d{1,2}\s*月|Q[1-4]|第?[一二三四1-4]\s*季|[上下]半年|TTM|LTM|去年|今年|本季|上季|本月|上月",
    re.I,
)
_NON_AMOUNT = re.compile(r"每股|/\s*股|per\s*share|EPS|率|比例|占比|股數|股本|股息", re.I)
_FOREIGN = re.compile(r"USD|US\$|美元|美金|EUR|歐元|人民幣|CNY|RMB|JPY|日圓|港元|港幣|HKD", re.I)
_NON_ACTUAL = re.compile(r'假設|如果|若|倘若|預估|預測|預計|預期|未來|明年|情境|目標|推估|估計|並非|不是|不為|非實際')
_CHANGE_AMOUNT = re.compile(r"年增|年減|增加|減少|增長|成長|下降|下滑|增減|變動|差額")
_PARTIAL_YEAR = re.compile(r"前[一二三四五六七八九十0-9]+(?:個)?月|累計|截至|年初至今|YTD", re.I)
_ERROR_EXAMPLE = re.compile(r"錯誤示例|錯誤範例|誤寫|誤稱|錯寫|錯稱|不採用|不可採用|更正前")
_SCALES = {'十億': 1e9, 'billion': 1e9, 'b': 1e9, '百萬': 1e6, 'million': 1e6,
           '億': 1e8, '萬': 1e4, '元': 1.0, 'twd': 1.0}


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def _source(data: dict, metric: str, prefix: str):
    # Quote currency alone is not a financial reporting currency declaration.
    if str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return None
    periods = list(_PERIOD.finditer(prefix))
    if _PARTIAL_YEAR.search(prefix):
        return None
    if not periods:
        return None
    period = re.sub(r'\s+', '', periods[-1].group()).upper()
    if len(periods) > 1 and re.fullmatch(r'\s*[年至到~～–—-]+\s*', prefix[periods[-2].end():periods[-1].start()]):
        return None  # Multi-year ranges do not identify which endpoint an amount represents.
    if metric in {'自由現金流', 'FCF'}:
        # A dated/older TTM claim cannot borrow the current un-dated raw TTM value.
        if period != 'TTM' or any(re.search(r'\d|去年|今年', p.group()) for p in periods[:-1]):
            return None
        raw = _finite(data.get('free_cash_flow_raw'))
        return (raw, 'data.free_cash_flow_raw', raw, 'twd', 'TTM') if raw is not None else None
    if not re.fullmatch(r'20\d{2}年?', period):
        return None
    for contract in (data.get('unit_contract'), (data.get('quant_metrics') or {}).get('unit_contract') if isinstance(data.get('quant_metrics'), dict) else None):
        if isinstance(contract, dict) and 'money' in contract and contract['money'] != 'billion_twd':
            return None
    year = period.removesuffix('年')
    years = data.get('years')
    field = 'revenue_history' if metric in {'營收', '營業收入'} else 'net_income_history'
    values = data.get(field)
    if not isinstance(years, list) or not isinstance(values, list) or len(years) != len(values):
        return None
    indexes = [i for i, y in enumerate(years) if str(y) == year]
    if len(indexes) != 1:
        return None
    i = indexes[0]; raw = _finite(values[i])
    # These canonical history arrays use billion_twd, as declared by the prompt
    # history contract. Never apply this adapter to arbitrary untyped objects.
    return (raw * 1e9, f'data.{field}[{i}]', raw, 'billion_twd', year) if raw is not None else None


def _amount_matches(number: str, scale: float, expected: float, negative_word: bool, uncertainty: float):
    raw = number.replace(',', '')
    reported = float(raw) * scale
    if negative_word and not raw.startswith(('-', '+')):
        reported = -reported
        raw = '-' + raw
    if not math.isfinite(reported):
        return True  # Non-finite/malformed numbers are outside this comparison.
    if abs(reported - expected) <= uncertainty:
        return True
    if abs(expected) <= uncertainty:
        return True  # Rounded annual zero cannot establish a sign or unit error.
    if reported == 0 or reported * expected < 0:
        return False
    if abs(reported - expected) / abs(expected) <= 0.01:
        return True
    # Allow actual displayed precision, rather than widening the 1% tolerance.
    precision = len(raw.partition('.')[2]) if '.' in raw else 0
    try:
        rounded = (Decimal(str(expected)) / Decimal(str(scale))).quantize(
            Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        if rounded == Decimal(raw):
            return True
    except InvalidOperation:
        return True
    # Only establish order-of-magnitude unit errors, not ordinary value differences.
    # Annual histories are rounded to 0.01 billion (yfinance_extractors), so a
    # comparison must also respect +/- 0.005 billion source uncertainty.
    for power in (1, 2, 3):
        for factor in (10.0 ** power, 10.0 ** -power):
            converted = reported * factor
            if abs(converted - expected) <= max(uncertainty, abs(expected) * 0.01):
                return False
    return True


def financial_money_claim_issues(text: str, data: dict | None) -> list[str]:
    """Return source-bound repair diagnostics; never rewrite a candidate."""
    if not isinstance(data, dict):
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or '')).replace('−', '-')
    clean = re.sub(r'[*`]', '', clean)
    issues = []
    for match in _AMOUNT.finditer(clean):
        start, end = match.span(); left, right = sentence_span(clean, start, end)
        prefix = clean[left:start]
        local_prefix = re.split(r'[，,、]|但是|然而|但', prefix)[-1]
        suffix = re.split(r'[，,、]|但是|然而|但', clean[end:right], maxsplit=1)[0]
        claim = match.group()
        if (re.search(r'分別|依序|各為', prefix + match['link'])
                or _NON_AMOUNT.search(local_prefix + match['link'])
                or re.match(r'\s*(?:%|股|/\s*股|倍)', clean[end:])
                or _FOREIGN.search(local_prefix + match['link'] + suffix)
                or _CHANGE_AMOUNT.search(match['link'])
                or '由' in match['link'] or _PERIOD.search(match['link'])
                or _ERROR_EXAMPLE.search(local_prefix + suffix)
                or _NON_ACTUAL.search(re.split(r'但是|然而|但|實際|實績', prefix)[-1] + match['link'])
                or _NON_ACTUAL.search(section_heading(clean, start))
                or re.match(r'[」\"）)\s]*(?:是|為|屬於)?(?:假設|預估|預測|目標)', suffix)):
            continue
        source = _source(data, match['metric'].upper(), prefix)
        if source is None:
            continue
        expected, path, original, unit, period = source
        name = match['unit'].lower()
        scale = _SCALES.get(name.removesuffix('元'), _SCALES.get(name))
        if scale is None or not math.isfinite(expected):
            continue
        if _amount_matches(match['number'], scale, expected, '負' in match['link'],
                           5e6 if unit == 'billion_twd' else 0):
            continue
        issues.append(
            f'財務金額單位紅線：{period} {match["metric"]} 原文「{claim}」與同期間來源不符；'
            f'來源 {path} 原值={original:g} {unit}，正確換算為{expected / 1e8:g}億新台幣。'
            '請核對原值、單位與期間後重新生成，不得將其他年度、TTM或推估數字混用。')
    return list(dict.fromkeys(issues))
