"""Bind explicit annual endpoints and exact same-year monthly enumerations.

This adapter supplies claims to the existing source/period/unit checker. It
never invents periods for nearby amounts or establishes primary-source truth.
"""
from __future__ import annotations

import math
import re

from financial_claim_context import CONDITIONAL, PROJECTION, THRESHOLD, is_actual_claim, sentence_span
from financial_money_claims import _FOREIGN, _NUMBER, _PERIOD, _target_revenue_scope

_UNIT = r'(?:十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)'
_MONEY = rf'{_NUMBER}\s*{_UNIT}(?:_twd|\s*(?:新[臺台]幣|[臺台]幣|NTD|TWD))?(?![A-Za-z_])'
_MONEY_PARTS = re.compile(rf'(?P<number>{_NUMBER})\s*(?P<unit>{_UNIT})', re.I)
_ALIAS = rf'\s*[（(]\s*{_MONEY}\s*[）)]'
_ANNUAL = re.compile(
    r'(?P<first_year>20\d{2})\s*年?\s*(?:至|到)\s*(?P<last_year>20\d{2})\s*年\s*'
    r'(?P<metric>自由現金流|FCF|營業收入|營收|稅後淨利|淨利)\s*(?:自|由|從)\s*'
    rf'(?P<first>{_MONEY})(?P<first_alias>{_ALIAS})?\s*'
    r'(?:增長|成長|增加|提升|下降|減少|下滑|躍升)?(?:至|到)\s*'
    rf'(?P<last>{_MONEY})(?P<last_alias>{_ALIAS})?', re.I,
)
_MONTHLY = re.compile(
    r'(?P<year>20\d{2})\s*年\s*(?P<first_month>1[0-2]|0?[1-9])\s*月\s*'
    r'(?:至|到)\s*(?P<last_month>1[0-2]|0?[1-9])\s*月\s*'
    r'(?:單月|各月|每月)\s*(?P<metric>營業收入|營收)\s*(?:分別|依序)為\s*'
    rf'(?P<amounts>{_MONEY}(?:\s*[、與和及]\s*{_MONEY})*)', re.I,
)
_MONTHLY_RANGE = re.compile(
    r'(?P<range_year>20\d{2})\s*年\s*近\s*(?P<range_count>1[0-2]|[1-9])\s*(?:個)?月\s*單月\s*'
    r'(?P<metric>營業收入|營收)\s*(?:在|介於)\s*'
    rf'(?P<first>{_MONEY})(?P<first_alias>{_ALIAS})?\s*(?:至|到|~|～)\s*'
    rf'(?P<last>{_MONEY})(?P<last_alias>{_ALIAS})?', re.I,
)
_POSTFIX_PROFIT = re.compile(
    r'(?P<metric>稅後淨利|淨利)\s*(?:自|由|從)\s*'
    rf'(?P<first>{_MONEY})(?P<first_alias>{_ALIAS})?\s*'
    r'(?:增長|成長|增加|提升|下降|減少|下滑|躍升)?(?:至|到)\s*'
    rf'(?P<last>{_MONEY})(?P<last_alias>{_ALIAS})?'
    r'(?P<citation>\s*。?\s*[（(]\s*來源\s*[:：]\s*history\.rows\s*[；;]\s*'
    r'(?P<first_year>20\d{2})\s*[-至]\s*(?P<last_year>20\d{2})\s*年\s*歷史損益表\s*[）)])?', re.I,
)
_MONEY_TOKEN = re.compile(_MONEY, re.I)
_PROJECTION_EN = re.compile(r'forecast|project(?:ed|ion)|estimate(?:d)?|scenario|assumption', re.I)
_FOREIGN_DECLARATION = re.compile(
    r'^\s*[，,]\s*(?:單位|幣別|currency|denominated)\s*(?:為|是|[:：]|in)?\s*'
    r'(?:美元|美金|USD|US\$|EUR|歐元|人民幣|CNY|RMB|JPY|日圓|HKD|港幣)', re.I,
)
_PER_SHARE = re.compile(r'^\s*(?:%|股|/\s*股|倍|per\s*share)', re.I)
_METRIC = re.compile(r'自由現金流|FCF|營業收入|營收|稅後淨利|淨利|毛利率|營業利益率', re.I)
_EXTRA_AMOUNT = re.compile(rf'\s*(?:至|到|或|~|～|、|與|和|及|[，,]\s*(?:或|及|與|和|or|and)?|[（(])\s*(?P<amount>{_MONEY})', re.I)
_EXTRA_LINK = re.compile(rf'^\s*(?:至|到|或|~|～|、|與|和|及|[，,]\s*(?:(?:或|及|與|和|or|and)\s*)?(?={_MONEY})|[（(]\s*[+\-\d])', re.I)
_LIST_ITEM = re.compile(r'^(?P<indent>\s*)(?:[-+*]|\d+[.)])\s+')
_MAX_NUMBER_LENGTH = 64
_PROVIDER_RATIO = re.compile(
    rf'(?:反證\s*[:：]\s*)?(?:資料集顯示\s*)?Yahoo\s*(?:即期|近期)\s*'
    rf'(?:營收|獲利)成長率(?:欄位)?(?:呈現|為)\s*{_NUMBER}\s*%', re.I,
)
_NON_ENTITY_DESCRIPTION = re.compile(
    r'(?:獲利能力|營運規模|營收表現|現金流表現|財務表現)'
    r'(?:顯著|持續|明顯)?(?:提升|拉升|改善|下降|惡化)'
)


def _clean_owner(owner):
    owner = re.sub(r'^\s*(?:[-+*]|\d+[.)])?\s*(?:發現|支持證據|證據比對|具體佐證)\s*[:：]\s*', '', owner)
    owner = re.sub(r'^\s*(?:且|並且|而|同時|然而|但是)\s*', '', owner)
    return owner.strip()


def financial_series_owner_matches(claim, data):
    """New period bindings require a known target or an implicit own subject.

    The caller must fail closed before looking up an annual/monthly value when
    this returns False. Non-series claims retain their existing rules.
    """
    if not claim.get('financial_series'):
        return True
    owner = str(claim.get('financial_series_owner') or '')
    heading = str(claim.get('financial_heading') or '')
    if not _target_revenue_scope(data, owner, heading):
        return False
    if _target_revenue_scope(data, owner, heading, require_explicit=True):
        return True
    # An implicit subject does not erase a peer or unknown issuer in the
    # preceding clause. A provider-labelled ratio is not a company identity.
    inherited = str(claim.get('financial_series_inherited_scope') or '')
    preceding = inherited + '\n' + str(claim.get('financial_series_owner_context') or '')
    for clause in reversed(re.split(r'[，,、\n]|但是|然而|但', preceding)[:-1]):
        clause = _clean_owner(clause)
        if _PROVIDER_RATIO.fullmatch(clause) or _NON_ENTITY_DESCRIPTION.fullmatch(clause):
            continue
        metric = _METRIC.search(clause)
        subject = clause[:metric.start()] if metric else clause
        if re.fullmatch(r'資料集顯示\s+Yahoo\s+即期\s*', subject, re.I):
            continue
        if not _target_revenue_scope(data, subject, heading):
            return False
        if _target_revenue_scope(data, subject, heading, require_explicit=True):
            return True
    return True


def _claims_for_match(line, raw, line_number, heading, inherited, match, kind):
    left, right = sentence_span(line, *match.span())
    owner_context = line[left:match.start()]
    owner = _clean_owner(re.split(r'[，,、]|但是|然而|但', owner_context)[-1])
    suffix = line[match.end():right]
    local_suffix = re.split(r'[，,]', suffix, maxsplit=1)[0]
    local = owner + match[0] + local_suffix
    actual = (is_actual_claim(line, *match.span())
              and not any(pattern.search(heading + '\n' + inherited) for pattern in (PROJECTION, THRESHOLD, CONDITIONAL, _PROJECTION_EN))
              and not _PROJECTION_EN.search(local))
    foreign = bool(_FOREIGN.search(heading + inherited + owner_context + local) or _FOREIGN_DECLARATION.search(suffix))
    if kind in {'annual_endpoints', 'postfix_annual_endpoints', 'monthly_range'}:
        first = int(match['first_year']) if kind != 'monthly_range' and match['first_year'] else None
        last = int(match['last_year']) if kind != 'monthly_range' and match['last_year'] else None
        incomplete = _EXTRA_LINK.match(suffix)
        bound = first is not None and last is not None and first < last and not incomplete
        if kind == 'postfix_annual_endpoints':
            # A citation is the only annual binder here; a local TTM/year is
            # incompatible, while complete preceding ratios own their dates.
            bound = bool(bound and match['citation'] and not _PERIOD.search(owner))
        if kind == 'monthly_range':
            bound = bool(int(match['range_count']) == 6 and not incomplete
                         and re.match(r'^\s*(?:區間|之間)', suffix)
                         and not _PERIOD.search(owner)
                         and not re.search(r'最新|截至|今日|目前', owner))
        values = []
        for endpoint, year, side in (('first', first, 'lower'), ('last', last, 'upper')):
            extra_fields = ({'financial_range_year': int(match['range_year']),
                             'financial_range_count': int(match['range_count']),
                             'financial_range_side': side} if kind == 'monthly_range' else {})
            values.append((match[endpoint], f'{year}年' if year is not None else '', extra_fields))
            if alias := match[endpoint + '_alias']:
                primary = _MONEY_PARTS.match(match[endpoint])
                reference = ({'financial_range_primary': {'number': primary['number'], 'unit': primary['unit']}}
                             if kind == 'monthly_range' else {})
                values.append((alias.lstrip().lstrip('（(').strip(), f'{year}年' if year is not None else '',
                               {**extra_fields, **reference}))
    else:
        first, last = int(match['first_month']), int(match['last_month'])
        amounts = list(_MONEY_TOKEN.finditer(match['amounts']))
        # Partial enumeration, reverse interval, or an extra unparsed list
        # item must leave *all* months unresolved, including matching values.
        incomplete = _EXTRA_LINK.match(suffix)
        bound = first <= last and len(amounts) == last - first + 1 and not incomplete
        values = [(amount[0], f"{match['year']}年{first + index}月" if bound else '', {})
                  for index, amount in enumerate(amounts)]
    # A range/alternative after the apparent last item invalidates the whole
    # mapping, but every extra numeric amount still belongs in the denominator.
    extra_end = 0
    while extra := _EXTRA_AMOUNT.match(suffix, extra_end):
        values.append((extra['amount'], '', {}))
        extra_end = extra.end()
        bound = False
    parsed_values = []
    for value, period, extra_fields in values:
        money = _MONEY_PARTS.match(value)
        number = money['number']
        normalized = number.replace(',', '')
        invalid = 'numeric_token_too_long' if len(normalized) > _MAX_NUMBER_LENGTH else ''
        if not invalid and len(number.partition('.')[2]) > 20:
            invalid = 'numeric_precision_out_of_bounds'
        parsed = float(normalized) if not invalid else None
        if parsed is not None and not math.isfinite(parsed):
            invalid, parsed = 'non_finite_numeric_token', None
        if invalid:
            bound = False
        parsed_values.append((money, number, parsed, period, invalid, extra_fields))
    claims = []
    for money, number, parsed, period, invalid, extra_fields in parsed_values:
        claims.append({
            'label': match['metric'].upper(), 'reported_value': parsed,
            'unit': money['unit'], 'claim_type': 'financial', 'financial_amount': True,
            'financial_metric': match['metric'].upper(),
            'financial_period_text': owner + ' ' + period if bound else '',
            'financial_owner_text': owner,
            'financial_heading': heading, 'financial_actual': bool(actual),
            'financial_display_precision': len(number.partition('.')[2]),
            'financial_scope_unbound': not bound, 'foreign_currency_declared': foreign,
            'line_number': line_number, 'raw_text': raw,
            'financial_series': kind, 'financial_series_owner': owner,
            'financial_series_owner_context': owner_context,
            'financial_series_inherited_scope': inherited,
            'financial_series_span': list(match.span()),
            **extra_fields,
            **({'financial_series_invalid_number': invalid,
                'financial_series_amount_text': number} if invalid else {}),
        })
    # Only the legacy first amount tied to this exact local metric scope is
    # superseded. Equal numbers elsewhere in the same line remain untouched.
    legacy_prefix = line[left:match.start('metric')]
    # Used only to match/remove the legacy first token. A non-finite legacy
    # float is never placed in the returned claim or serialized evidence.
    legacy_value = float(parsed_values[0][1].replace(',', ''))
    return claims, legacy_prefix, legacy_value


def extract_financial_series(markdown, existing):
    """Replace the legacy first amount and add every explicit ordered item.

    Call after extract_financial_amounts. The owner predicate above must also
    run in the financial checker; no source lookup occurs during extraction.
    """
    result = list(existing)
    in_code = False
    heading = ''
    paragraph = ''
    list_scopes = []
    for line_number, raw in enumerate(str(markdown or '').splitlines(), 1):
        if raw.strip().startswith('```'):
            in_code = not in_code
            paragraph = ''
            list_scopes = []
            continue
        if in_code:
            continue
        line = re.sub(r'[*`]', '', raw).replace('−', '-')
        if not line.strip():
            if not paragraph.rstrip().endswith((':', '：')):
                paragraph = ''
            # Markdown permits a blank line inside a parent list item. Its
            # subject/currency remains active for an indented child item.
            continue
        if line.lstrip().startswith('#'):
            heading = line
            paragraph = ''
            list_scopes = []
            continue
        item = _LIST_ITEM.match(raw)
        indent = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
        if item:
            while list_scopes and indent <= list_scopes[-1][0]:
                list_scopes.pop()
            inherited = list_scopes[-1][1] if list_scopes else paragraph
            list_scopes.append((indent, inherited + line + '\n'))
        elif list_scopes and indent > list_scopes[-1][0]:
            inherited = list_scopes[-1][1]
            list_scopes[-1] = (list_scopes[-1][0], inherited + line + '\n')
        else:
            list_scopes = []
            inherited = paragraph
            paragraph += line + '\n'
        annual_spans = [match.span() for match in _ANNUAL.finditer(line)]
        for pattern, kind in ((_ANNUAL, 'annual_endpoints'), (_MONTHLY, 'monthly_enumeration'),
                              (_MONTHLY_RANGE, 'monthly_range'), (_POSTFIX_PROFIT, 'postfix_annual_endpoints')):
            for match in pattern.finditer(line):
                if kind == 'postfix_annual_endpoints' and any(start <= match.start() < end for start, end in annual_spans):
                    continue
                if _PER_SHARE.match(line[match.end():]):
                    continue
                additions, legacy_prefix, legacy_value = _claims_for_match(line, raw, line_number, heading, inherited, match, kind)
                if not additions:
                    continue
                first = additions[0]
                result = [claim for claim in result if not (
                    claim.get('line_number') == line_number
                    and claim.get('financial_metric') == first['financial_metric']
                    and ((claim.get('financial_series') == kind
                          and claim.get('financial_series_span') == list(match.span()))
                         or (claim.get('reported_value') == legacy_value
                             and str(claim.get('unit', '')).lower() == first['unit'].lower()
                             and claim.get('financial_period_text') == legacy_prefix))
                )]
                result.extend(additions)
    return [{**claim, 'id': index + 1} for index, claim in enumerate(result)]
