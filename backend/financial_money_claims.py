"""Bounded money-unit checks against annual histories and an undated FCF input.

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
    r"(?P<metric>自由現金流|FCF|營業收入|營收|淨收益|本期損益|稅後淨利|淨利)"
    r"(?P<link>(?:(?!自由現金流|FCF|營業收入|營收|淨收益|本期損益|稅後淨利|淨利)[^\d。；;，,\n]){0,35}?)"
    rf"(?P<number>{_NUMBER})\s*"
    r"(?P<unit>十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)"
    r"(?![A-Za-z])", re.I,
)
# Equity is admitted only for the fully replayed ordinary-individual contract;
# existing schemas keep their original bounded monetary checker.
_INDIVIDUAL_AMOUNT = re.compile(_AMOUNT.pattern.replace('稅後淨利|淨利','稅後淨利|淨利|權益總額|權益'),re.I)
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

_UNIT_DEFINITION = re.compile(r'\bBillion\s+TWD\s*[（(]\s*(?P<number>10)\s*億(?:台幣|新臺幣|元)\s*[)）]', re.I)


def is_unit_definition_number(line, start, end):
    """Only the exact 1-billion = 10-億 definition, never a company amount."""
    return any(match.span('number') == (start, end) for match in _UNIT_DEFINITION.finditer(line))


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
    statement = data.get('sector_specific_financials')
    insurer = isinstance(statement, dict) and statement.get('schema') == 'insurer_standalone.v1'
    individual=isinstance(statement,dict)and statement.get('schema')=='ordinary_individual.v1'
    if individual:
        from data_fetch.financial_history_basis import prompt_history_basis
        if prompt_history_basis(data).get('statement_schema')!='ordinary_individual.v1':return None
    if insurer or metric == '本期損益' and not individual:
        from data_fetch.financial_history_basis import prompt_history_basis
        if prompt_history_basis(data).get('statement_schema') != 'insurer_standalone.v1':
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
        # Retain numeric unit rejection without certifying the scalar's period.
        if period != 'TTM' or any(re.search(r'\d|去年|今年', p.group()) for p in periods[:-1]):
            return None
        raw = _finite(data.get('free_cash_flow_raw'))
        return (raw, 'data.free_cash_flow_raw', raw, 'twd', '即期輸入（期間未核實）') if raw is not None else None
    if not re.fullmatch(r'20\d{2}年?', period):
        return None
    for contract in (data.get('unit_contract'), (data.get('quant_metrics') or {}).get('unit_contract') if isinstance(data.get('quant_metrics'), dict) else None):
        if isinstance(contract, dict) and 'money' in contract and contract['money'] != 'billion_twd':
            return None
    year = period.removesuffix('年')
    years = data.get('years')
    if metric in {'權益總額','權益'}:
        if not individual:return None
        field='total_equity_history'
    elif metric == '淨收益':
        from data_fetch.financial_history_basis import prompt_history_basis, INSTITUTION_SCHEMAS
        if prompt_history_basis(data).get('statement_schema') not in INSTITUTION_SCHEMAS:
            return None
        field = 'net_revenue_history'
    else:
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


def _target_revenue_scope(data: dict, prefix: str, heading: str) -> bool:
    """Only target or implicit own-company clauses can borrow its new FI facts."""
    from source_content_selection import company_aliases
    scope = _PERIOD.sub('', prefix)
    explicit = bool(re.search(r'本公司|本集團|本行|本標的', scope))
    ticker = re.fullmatch(r'(\d{4})\.TW(?:O)?', str(data.get('ticker') or ''))
    if ticker:
        code_pattern = r'(?<![0-9A-Za-z])' + ticker[1] + r'(?:\.TW(?:O)?)?(?![0-9A-Za-z])'
        scope, matches = re.subn(code_pattern, '', scope, flags=re.I)
        explicit = explicit or bool(matches)
    for alias in sorted(company_aliases(data), key=len, reverse=True):
        pattern = (re.escape(alias) if re.search(r'[\u3400-\u9fff]', alias)
                   else r'(?<!\w)' + re.escape(alias) + r'(?!\w)')
        scope, matches = re.subn(pattern, '', scope, flags=re.I)
        explicit = explicit or bool(matches)
    if re.search(r'同業|同儕|競爭(?:者|對手)|peer|competitor', heading, re.I) and not explicit:
        return False
    scope = re.sub(r'本公司|本集團|本行|本標的|根據|依據|按|資料|財報|年報|合併|集團|年度|全年|顯示|指出|公布|公告|實際|記錄|之|的|於|為|年', '', scope)
    # Remaining entity/prose is ambiguous, never presumed to be our issuer.
    return not re.sub(r'[\W_]+', '', scope)


def financial_money_claim_issues(text: str, data: dict | None) -> list[str]:
    """Return source-bound repair diagnostics; never rewrite a candidate."""
    if not isinstance(data, dict):
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or '')).replace('−', '-')
    clean = re.sub(r'[*`]', '', clean)
    issues = []
    statement = data.get('sector_specific_financials')
    insurer = isinstance(statement, dict) and statement.get('schema') == 'insurer_standalone.v1'
    individual=isinstance(statement,dict)and statement.get('schema')=='ordinary_individual.v1'
    for match in (_INDIVIDUAL_AMOUNT if individual else _AMOUNT).finditer(clean):
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
        target_scope = None
        if match['metric'] == '淨收益':
            target_scope = _target_revenue_scope(data, local_prefix, section_heading(clean, start))
            if not target_scope:
                continue
        source = _source(data, match['metric'].upper(), prefix)
        if individual and source is not None and re.search(r'合併|集團|母公司',local_prefix+match['link']):
            issuer_prefix=re.sub(r'個別|合併|集團|母公司','',local_prefix)
            if _target_revenue_scope(data,issuer_prefix,section_heading(clean,start)):
                issues.append(f'一般業個別財報範圍紅線：{source[-1]} 原文「{claim}」使用合併、集團或母公司口徑；本次原件採個別本期損益及權益，未證明集團口徑。')
                continue
        if insurer and source is not None:
            issuer_prefix = re.sub(r'個別|母公司', '', local_prefix)
            if not _target_revenue_scope(data, issuer_prefix, section_heading(clean, start)):
                continue
            if re.search(r'合併|母公司', local_prefix + match['link']):
                issues.append(
                    f'保險業財報範圍紅線：{source[-1]} 原文「{claim}」使用合併或母公司口徑；'
                    '本次原件逐年明示無子公司，採個別財報營業收入及本期損益。請保留個別範圍。')
                continue
        if source is None:
            if match['metric'] in {'營收', '營業收入'}:
                typed_source = _source(data, '淨收益', prefix)
                if (typed_source is not None
                        and _target_revenue_scope(data, local_prefix, section_heading(clean, start))):
                    issues.append(
                        f'金融業科目口徑紅線：{typed_source[-1]} 原文「{claim}」稱為{match["metric"]}，'
                        '本次已驗證序列採金融業獨立淨收益科目，未提供一般產業營收序列。'
                        '請依 financial_history_basis 與原件科目重新生成，不得將淨收益改稱營業收入。')
            continue
        expected, path, original, unit, period = source
        name = match['unit'].lower()
        scale = _SCALES.get(name.removesuffix('元'), _SCALES.get(name))
        if scale is None or not math.isfinite(expected):
            continue
        if _amount_matches(match['number'], scale, expected, '負' in match['link'],
                           5e6 if unit == 'billion_twd' else 0):
            continue
        comparison = '保存的即期輸入不符；此處只核對數值換算，期間未核實' if path == 'data.free_cash_flow_raw' else '同期間來源不符'
        issues.append(
            f'財務金額單位紅線：{period} {match["metric"]} 原文「{claim}」與{comparison}；'
            f'來源 {path} 原值={original:g} {unit}，正確換算為{expected / 1e8:g}億新台幣。'
            '請核對原值、單位與期間後重新生成，不得將其他年度、TTM或推估數字混用。')
    # Reuse the period-aware evidence adapter for annual FCF and named TTM
    # amounts, which the original annual-revenue checker does not admit.
    from report_financial_errata import money_unit_mismatches
    for claim in money_unit_mismatches(text, {'data': data}):
        if _source(data, claim['financial_metric'], claim['financial_period_text']) is not None:
            continue
        issues.append(
            f'財務金額單位紅線：{claim["financial_period"]} {claim["financial_metric"]} '
            f'原值={claim["source_value"]:g} {claim["source_unit"]}，來源 {claim["matched_path"]}；'
            f'正確換算為{claim["expected_value_raw_twd"] / 1e8:g}億新台幣。請保留期間與科目後重新生成。')
    return list(dict.fromkeys(issues))
