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
_FINANCIAL_PREAMBLE = re.compile(r'財務(?:資料|數據)?(?:如下|概況|表現)|財報(?:顯示|指出)')
_SCALES = {'十億': 1e9, 'billion': 1e9, 'b': 1e9, '百萬': 1e6, 'million': 1e6,
           '億': 1e8, '萬': 1e4, '元': 1.0, 'twd': 1.0}

_UNIT_DEFINITION = re.compile(r'\bBillion\s+TWD\s*[（(]\s*(?P<number>10)\s*億(?:台幣|新臺幣|元)\s*[)）]', re.I)
TTM_MONEY_PROMPT_POLICY = 'ttm-money-reference:v2-bound-scalars'


def ttm_money_reference_prompt(data):
    """Arithmetic reference only; never certify the scalar's reporting period."""
    from financial_fact_binding import financial_reference_prompt
    if str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return ''
    raw = _finite(data.get('net_income_ttm_raw'))
    if raw is None:
        return ''
    return financial_reference_prompt(data)


def is_unit_definition_number(line, start, end):
    """Only the exact 1-billion = 10-億 definition, never a company amount."""
    return any(match.span('number') == (start, end) for match in _UNIT_DEFINITION.finditer(line))


def signed_amount_number(match):
    """Keep a unary sign before a currency prefix attached to its amount."""
    number = match['number']
    if not number.startswith(('-', '+')):
        sign = re.search(r'([+\-−])\s*(?:NT\$|NTD|TWD|\$)\s*$', match['link'], re.I)
        if sign:
            return sign[1].replace('−', '-') + number
        if '負' in match['link']:
            return '-' + number
        if (match['metric'] in {'淨利', '稅後淨利', '本期損益'}
                and re.search(r'(?:淨損|虧損)\s*(?:(?:約為?|達|為)\s*)?(?:NT\$|NTD|TWD|\$)?\s*$', match['link'], re.I)
                and not re.search(r'(?:並非|不是|非|未(?:轉為|出現|發生)?|無)\s*(?:淨損|虧損)', match['link'])):
            return '-' + number
        if (match['metric'].upper() in {'自由現金流', 'FCF'}
                and re.search(r'(?:(?:淨)?流出|缺口)\s*(?:(?:約為?|達|為)\s*)?(?:NT\$|NTD|TWD|\$)?\s*$', match['link'], re.I)
                and not re.search(r'(?:並非|不是|非|未(?:轉為|出現|發生)?|無)\s*(?:(?:淨)?流出|缺口)', match['link'])):
            return '-' + number
    return number


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def _official_ttm_followed_by_annual_period(data, prefix):
    """End one fully named source clause at its explicit next annual clause.

    This narrow source-owned form does not make a generic comma reset company,
    currency or period scope. The annual amount still uses its saved annual
    history; the preceding TTM original is never substituted for that year.
    """
    if re.search(r'合併|本集團|集團口徑', prefix) or _FOREIGN.search(prefix):
        return None
    match = re.fullmatch(
        r'(?P<owner>.*?)data\.cash_flow\.official_reference\s*顯示\s*TTM\s*'
        r'(?:自由現金流|FCF)\s*為\s*' + _NUMBER
        + r'\s*(?:億元?|billion_twd|十億元?)\s*[（(]\s*'
        r'(?P<start>20\d{2}-\d{2}-\d{2})\s*至\s*(?P<end>20\d{2}-\d{2}-\d{2})\s*[）)]'
        r'\s*[，,]\s*(?:且|而|另外)?\s*(?P<year>20\d{2})\s*年度\s*', prefix, re.I)
    explicit_owner = False
    if match is None:
        # The rendered final synthesis names the issuer and individual scope
        # directly and places the TTM dates before the FCF abbreviation. Its
        # cash-flow component parentheses belong to that preceding amount.
        match = re.fullmatch(
            r'(?P<owner>.*?)個別\s*(?P<start>20\d{2}-\d{2}-\d{2})\s*至\s*'
            r'(?P<end>20\d{2}-\d{2}-\d{2})\s*TTM\s*(?:自由現金流|FCF)\s*為\s*' + _NUMBER
            + r'\s*億元\s*[（(]營業現金流\s*' + _NUMBER + r'\s*億元\s*[、,，]\s*資本支出\s*'
            + _NUMBER + r'\s*億元[）)]\s*[，,]\s*(?P<year>20\d{2})\s*年\s*單年度\s*', prefix, re.I)
        explicit_owner = True
    if match is None:
        return None
    owner = re.split(r'[。；;\n]', match['owner'])[-1] if explicit_owner else match['owner']
    # A generated risk bullet has a bounded topic/metadata prefix. Arbitrary
    # names or prose before the source path must retain their owner scope.
    topics = r'(?:自由現金流|持續|淨流出|流動性|壓力|風險|財務|營運|與|及|和)+'
    owner = re.sub(
        r'^\s*[-*]?\s*' + topics + r'\s*[（(]嚴重度\s*[:：]\s*(?:critical|high|warning|medium|low)'
        r'\s*[；;]\s*信心\s*[（(]0[–-]1[）)]\s*[:：]\s*(?:0(?:\.\d+)?|1(?:\.0+)?)\s*[）)]\s*[:：]\s*',
        '', owner, flags=re.I)
    if not _target_revenue_scope(data, owner, '', require_explicit=explicit_owner):
        return None
    from official_financial_projection import read_official_financial_projection
    selected = read_official_financial_projection(data)
    if selected is None:
        return None
    facts = selected['facts']
    if (match['start'], match['end']) != (facts['period_start'], facts['period_end']):
        return None
    return match['year'] + '年'


def financial_period_scope(data: dict, prefix: str) -> str | None:
    """Bind an explicit annual clause without inheriting a preceding TTM claim.

    Relative latest-year wording refers only to the saved annual-year catalog,
    not the current calendar or a claim that the source is independently latest.
    """
    from financial_local_amounts import clean_observed_prefix, completed_annual_clause
    prefix = clean_observed_prefix(prefix, data)
    if local_annual := completed_annual_clause(data, prefix):
        return local_annual
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    if not re.search(r'年度|全年', local):
        return prefix
    if annual := _official_ttm_followed_by_annual_period(data, prefix):
        return annual
    prefix = _issuer_subject_scope(data, prefix)
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    before = prefix[:len(prefix) - len(local)]
    causal = re.match(r'^\s*(?:且\s*)?(?:主因為|主因是)\s*', local)
    if causal:
        # A causal connective is not a company name. Keep every actual owner,
        # currency and period qualifier after it, and do not discard an unknown
        # subject before the clause merely because the new clause names a year.
        local = local[causal.end():]
        if re.search(r'合併|本集團|集團口徑', local) or _FOREIGN.search(prefix):
            return None
        valuation_topic = re.fullmatch(
            r'\s*[-*]?\s*內在價值計算限制\s*[:：]\s*根據\s*quant_metrics\.v2\s*[，,]\s*'
            r'DCF\s*狀態為\s*unavailable\s*[。.]\s*', before, re.I)
        if (before.strip() and not _AMOUNT.search(before) and not valuation_topic
                and not _target_revenue_scope(data, before, '')):
            return None
    if not _annual_owner_scope(data, before, local):
        return None
    latest = re.search(r'(?:最新|最近)(?:完整)?(?:全年度|年度|全年)', local)
    # A prior amount has its own period. A period-only preamble still scopes
    # this amount and cannot be silently replaced with the latest catalog year.
    amounts = list(_AMOUNT.finditer(before))
    preamble = before[amounts[-1].end():] if amounts else before
    if _PERIOD.search(preamble):
        return None if latest else preamble + local
    periods = list(_PERIOD.finditer(local))
    if periods:
        return local if all(re.fullmatch(r'20\d{2}年?', re.sub(r'\s+', '', item[0])) for item in periods) else None
    if latest is None:
        return None
    if not _target_revenue_scope(data, local[:latest.start()], ''):
        return None
    years = data.get('years')
    if (not isinstance(years, list) or not years
            or any(not re.fullmatch(r'20\d{2}', str(year)) for year in years)
            or len({str(year) for year in years}) != len(years)):
        return None
    year = max(str(year) for year in years)
    return local[:latest.start()] + year + '年' + local[latest.end():]


def _annual_owner_scope(data, before, local):
    """Carry the nearest financial subject until an explicit issuer replaces it."""
    owner = re.sub(
        rf'{_NUMBER}\s*(?:十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)(?:_twd)?'
        r'\s*的(?:年度|全年)?(?:營業收入|營收|淨利|自由現金流|FCF)\s*(?:與|及|和|、)?', '', local, flags=re.I)
    if _target_revenue_scope(data, owner, '', require_explicit=True):
        return True
    if not _target_revenue_scope(data, owner, ''):
        return False
    for clause in reversed(re.split(r'[，,、。；;\n]|但是|然而|但', before)):
        amount = _AMOUNT.search(clause)
        preamble = _FINANCIAL_PREAMBLE.search(clause)
        boundary = amount or preamble
        if boundary is None:
            continue
        owner = clause[:boundary.start()]
        # Colon-delimited risk topics are labels, not company identities.
        # Unknown names (including a peer before a colon) remain in the scope.
        pieces = re.split(r'[:：]', owner)
        topics = r'(?:已納入考量的)?(?:現金流|償債|再融資|營運|財務|壓力|風險|與|及|和|的)+'
        owner = ':'.join(piece for piece in pieces if not re.fullmatch(
            r'\s*[-*]?\s*' + topics + r'\s*', piece))
        if _target_revenue_scope(data, owner, '', require_explicit=True):
            return True
        if not _target_revenue_scope(data, owner, ''):
            return False
    return True


def _source(data: dict, metric: str, prefix: str):
    if other_financial_owner(data, prefix):
        return None
    prefix = financial_period_scope(data, prefix)
    if prefix is None:
        return None
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


def _target_revenue_scope(data: dict, prefix: str, heading: str, *, require_explicit: bool = False) -> bool:
    """Only target or implicit own-company clauses can borrow its new FI facts."""
    from source_content_selection import company_aliases
    prefix = re.sub(r'對照(?:本公司|公司|本集團|本標的)', '本公司', prefix)
    scope = _PERIOD.sub('', re.sub(r'(20\d{2})\s*年度', r'\1年', prefix))
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
    scope = re.sub(r'(?:最新|最近)(?:完整)?(?:全年度|年度|全年)', '', scope)
    scope = re.sub(r'本公司|本集團|本行|本標的|根據|依據|按|財務(?:資料|數據)|最新|資料|財報|年報|合併|集團|年度|全年|顯示|指出|公布|公告|實際|已實現|記錄|之|的|於|為|年', '', scope)
    # Remaining entity/prose is ambiguous, never presumed to be our issuer.
    return (explicit or not require_explicit) and not re.sub(r'[\W_]+', '', scope)


def other_financial_owner(data, prefix, heading=''):
    """A named peer cannot borrow the issuer's financial scalar or history."""
    peer = r'同業|同儕|競爭(?:者|對手)|peer|competitor'
    if not re.search(peer, prefix + heading, re.I):
        return False
    own_start = _issuer_subject_start(data, prefix)
    if own_start is not None:
        prefix = prefix[own_start:]
    if not re.search(peer, prefix, re.I) and (own_start is not None or not re.search(peer, heading, re.I)):
        return False
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    return not _target_revenue_scope(data, local, heading, require_explicit=True)


def _issuer_subject_scope(data, prefix):
    """An explicit new issuer subject ends the preceding peer/period scope."""
    start = _issuer_subject_start(data, prefix) or 0
    before = prefix[:start]
    amounts = list(_AMOUNT.finditer(before))
    preamble = before[amounts[-1].end():] if amounts else before
    # An issuer noun does not cancel an amountless period preamble for the
    # same claim. Only a preceding different financial subject ends that scope.
    if (_PERIOD.search(preamble) and _annual_owner_scope(data, preamble, '')
            and not re.search(r'同業|同儕|競爭(?:者|對手)|peer|competitor', preamble, re.I)):
        return preamble + prefix[start:]
    return prefix[start:]


def _issuer_subject_start(data, prefix):
    boundaries = [0, *(match.end() for match in re.finditer(r'[，,、。；;\n]|但是|然而|但', prefix))]
    start = None
    for left, right in zip(boundaries, boundaries[1:] + [len(prefix)]):
        clause = prefix[left:right]
        boundary = _AMOUNT.search(clause) or _FINANCIAL_PREAMBLE.search(clause)
        owner = clause[:boundary.start()] if boundary else clause
        if _target_revenue_scope(data, owner, '', require_explicit=True):
            start = left
    return start


def revenue_segment_scope(prefix: str, heading: str = '', parent: str = '', *, data: dict | None = None) -> bool:
    """Explicit product/segment revenue cannot borrow an issuer total.

    This is an exclusion from the total comparator, not segment verification.
    An explicitly new total subject can end an inherited segment context.
    """
    segment = r'產品(?:線|別)?|分部|部門|事業(?:部|群)|業務(?:部|線|別)|(?:特高壓|超高壓|中高壓|低壓|橡膠|電力|高壓)?電纜'
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    markers = list(re.finditer(segment, local))
    total = r'(?:20\d{2}\s*年?\s*)?(?:全年|年度)?\s*(?:總額|合計|總|整體)\s*$'
    if markers:
        # "產品組合...公司2025年總營收" names a new issuer total;
        # "產品合計營收" is still only the product subtotal.
        return not re.search(r'(?:本公司|全公司|公司)\s*' + total,
                             local[markers[-1].end():])
    if re.search(total, local):
        return False
    if _target_revenue_scope(data or {}, local, '', require_explicit=True):
        return False  # A current issuer subject resets inherited product scope.
    # An industry name in a heading is background, not a revenue segment.
    # Preamble/list ownership remains narrower context for its child claim.
    segment_heading = r'分部|部門|事業(?:部|群)|業務(?:部|線|別)|產品(?:線|別)?(?:營收|收入)'
    return bool(re.search(segment_heading, heading) or re.search(segment, parent))


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
        actual_comparison = bool(re.fullmatch(
            r'\s*對照(?:本公司|公司|本集團|本標的)\s*20\d{2}\s*年?\s*(?:全年|年度)?\s*', local_prefix))
        if (re.search(r'分別|依序|各為', prefix + match['link'])
                or _NON_AMOUNT.search(local_prefix + match['link'])
                or re.match(r'\s*(?:%|股|/\s*股|倍)', clean[end:])
                or _FOREIGN.search(local_prefix + match['link'] + suffix)
                or _CHANGE_AMOUNT.search(match['link'])
                or '由' in match['link'] or _PERIOD.search(match['link'])
                or _ERROR_EXAMPLE.search(local_prefix + suffix)
                or _NON_ACTUAL.search(re.split(r'但是|然而|但|實際|實績', prefix)[-1] + match['link'])
                or (_NON_ACTUAL.search(section_heading(clean, start)) and not actual_comparison)
                or re.match(r'[」\"）)\s]*(?:是|為|屬於)?(?:假設|預估|預測|目標)', suffix)):
            continue
        target_scope = None
        if match['metric'] in {'營收', '營業收入'} and revenue_segment_scope(
                prefix, section_heading(clean, start), data=data):
            continue
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
        if _amount_matches(signed_amount_number(match), scale, expected, False,
                           5e6 if unit == 'billion_twd' else 0):
            continue
        comparison = '保存的即期輸入不符；此處只核對數值換算，期間未核實' if path == 'data.free_cash_flow_raw' else '同期間來源不符'
        issues.append(
            f'財務金額單位紅線：{period} {match["metric"]} 原文「{claim}」與{comparison}；'
            f'來源 {path} 原值={original:g} {unit}，正確換算為{expected / 1e8:g}億新台幣。'
            '請核對原值、單位與期間後重新生成，不得將其他年度、TTM或推估數字混用。')
    # Keep source-bound annual diagnostics when a completed TTM transition or
    # a bounded causal introduction is outside the old prose-only heuristic.
    from evidence_financial_amounts import check_financial_amount, extract_financial_amounts
    for claim in extract_financial_amounts(text, []):
        if claim.get('financial_capex'):
            checked = check_financial_amount(claim, {'data': data}, 1.0)
            if checked and checked['status'] == 'mismatch':
                issues.append(
                    f'財務金額單位紅線：{checked["financial_period"]} {checked["financial_definition"]} '
                    f'與官方同期間原件不符；支出原始正負值={checked["source_signed_raw_twd"]} TWD，'
                    f'現金支出金額應為{checked["expected_value_raw_twd"] / 1e8:g}億新台幣。'
                    '須分開年度與TTM、設備與含無形資產合計及流出方向，不得跨期間或省略缺少的組成。')
            continue
        period_text = claim.get('financial_period_text', '')
        local_period = re.split(r'[，,、。；;\n]|但是|然而|但', period_text)[-1]
        causal_annual = re.match(r'^\s*(?:且\s*)?(?:主因為|主因是)\s*', local_period)
        if (claim.get('financial_metric') not in {'FCF', '自由現金流'}
                or not (causal_annual or _official_ttm_followed_by_annual_period(data, period_text))):
            continue
        checked = check_financial_amount(claim, {'data': data}, 1.0)
        if checked and checked['status'] == 'mismatch':
            if checked.get('verification_reason_code') == 'financial_annual_direction_mismatch':
                issues.append(
                    f'財務金額單位紅線：{checked["financial_period"]} FCF 流入／流出方向與同年度來源正負號矛盾；'
                    f'來源 {checked["matched_path"]} 為{checked["expected_value_raw_twd"] / 1e8:g}億新台幣，'
                    '請保留期間及個別範圍，按來源正負號重新生成方向。')
                continue
            issues.append(
                f'財務金額單位紅線：{checked["financial_period"]} {claim["financial_metric"]} '
                f'與同年度保存來源不符；來源 {checked["matched_path"]} 原值={checked["source_value"]:g} '
                f'{checked["source_unit"]}，正確換算為{checked["expected_value_raw_twd"] / 1e8:g}億新台幣。'
                '各筆金額須使用各自明示期間與主體，不得混用年度及TTM，請保留來源範圍後重新生成。')
    # Reuse the period-aware evidence adapter for annual FCF and named TTM
    # amounts, which the original annual-revenue checker does not admit.
    from report_financial_errata import money_unit_mismatches
    for claim in money_unit_mismatches(text, {'data': data}):
        if (_source(data, claim['financial_metric'], claim['financial_period_text']) is not None
                and not claim.get('financial_series')):
            continue
        if claim.get('financial_range_comparison_reference') == 'reported_range_primary':
            issues.append(
                f'財務金額單位紅線：{claim["financial_period"]} {claim["financial_metric"]} '
                f'括號金額必須與原文界限一致，正確換算為{claim["expected_value_raw_twd"] / 1e8:g}億新台幣。'
                '這是原文界限的單位換算，非將資料來源的觀測極值改寫為該界限；請保留期間與科目後重新生成。')
            continue
        original = claim['source_value']
        rendered_original = f'{original:g}' if _finite(original) is not None else str(original)
        issues.append(
            f'財務金額單位紅線：{claim["financial_period"]} {claim["financial_metric"]} '
            f'原值={rendered_original} {claim["source_unit"]}，來源 {claim["matched_path"]}；'
            f'正確換算為{claim["expected_value_raw_twd"] / 1e8:g}億新台幣。請保留期間與科目後重新生成。')
    from financial_fact_binding import scalar_claim_issues
    issues.extend('財務金額單位紅線：' + issue + '；須核對原始欄位、主體、期間與幣別，不得用固定說明抵銷矛盾。'
                  for issue in scalar_claim_issues(text, data, require_available=False))
    return list(dict.fromkeys(issues))
