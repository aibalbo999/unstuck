"""Narrow presentation boundaries for observed financial amounts.

These helpers identify clauses, never supply values or certify a source.
Unknown subjects, currencies and period preambles remain in the binding text.
"""
from __future__ import annotations

import re


_QUOTE = re.compile(r'^\s*[-*]?\s*(?:成長|估值)分析引文\s*[:：]\s*')
_LABEL = re.compile(
    r'^\s*(?:[-*]|\d+[.)])?\s*(?:註|反證|發現|現金流持續承壓|'
    r'內在價值計算受限|獲利轉化現金效率低落|獲利品質風險)\s*[:：]\s*')
_CONSOLIDATED = re.compile(r'合併|集團|consolidated|group', re.I)


def amount_sentence_span(text: str, start: int, end: int) -> tuple[int, int]:
    """A dot inside a bounded source citation cannot hide its following scope."""
    from financial_claim_context import SENTENCE_BREAK
    citations = [match.span() for match in re.finditer(
        r'[（(]\s*來源\s*[:：][^()（）\n]{1,500}[）)]', text)]
    def separator(match):
        return not (match[0] == '.' and any(left <= match.start() < right for left, right in citations))
    left = 0
    for match in SENTENCE_BREAK.finditer(text, 0, start):
        if separator(match):
            left = match.end()
    for match in SENTENCE_BREAK.finditer(text, end):
        if separator(match):
            return left, match.start()
    return left, len(text)


def observed_quote_heading(heading: str, line: str) -> bool:
    """An assumption-comparison title does not turn its quoted past into future."""
    return bool(re.fullmatch(r'\s*#{1,6}\s*成長與估值假設對照\s*', heading)
                and _QUOTE.match(line))


def empirical_comparison_heading(heading: str) -> bool:
    """The report's evidence comparison section contains observed counterfacts."""
    return bool(re.fullmatch(r'\s*#{1,6}\s*(?:[一二三四五六七八九十\d]+[、.]\s*)?'
                             r'成長預期與媒體報導之實證落差\s*', heading))


def observation_prefix(text: str) -> str:
    """Only 'if we observe this dated statement', not a hypothetical result."""
    return re.sub(
        r'若觀察(?=\s*官方\s*個別\s*(?:財報\s*)?TTM\s*[（(]\s*'
        r'20\d{2}-\d{2}-\d{2}\s*至\s*20\d{2}-\d{2}-\d{2}\s*[）)])',
        '觀察', text, flags=re.I)


def clean_observed_prefix(prefix: str, data: dict) -> str:
    """Remove only structural labels and a named negative-FCF parenthesis."""
    from financial_money_claims import _target_revenue_scope
    if _CONSOLIDATED.search(prefix):
        return prefix
    parts = re.split(r'([。；;\n])', prefix)
    for index in range(0, len(parts), 2):
        value = _QUOTE.sub('', parts[index])
        for _ in range(3):
            value = _LABEL.sub('', value)
        value = re.sub(r'^\s*根據系統\s+deterministic\s+計算結果\s*[，,]\s*', '', value, flags=re.I)
        nested = re.fullmatch(r'(?P<owner>.*?)因自由現金流為負值\s*[（(]\s*(?P<period>20\d{2}\s*年度)\s*', value)
        if nested and _target_revenue_scope(data, nested['owner'], '', require_explicit=True):
            value = nested['owner'] + nested['period']
        value = re.sub(r'(20\d{2}\s*年度)\s*歷史\s*$', r'\1 ', value)
        parts[index] = value
    return ''.join(parts)


def completed_annual_clause(data: dict, prefix: str) -> str | None:
    """An absolute new year after a completed amount owns its own period."""
    from financial_money_claims import _AMOUNT, _PERIOD, _FOREIGN, _annual_owner_scope, _target_revenue_scope
    if _FOREIGN.search(prefix) or _CONSOLIDATED.search(prefix):
        return None
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    before = prefix[:len(prefix) - len(local)]
    absolute = re.fullmatch(r'\s*(?P<owner>.*?)?(?P<year>20\d{2})\s*年度\s*', local)
    relative = re.fullmatch(r'\s*同年度\s*', local)
    amounts = list(_AMOUNT.finditer(before))
    if not amounts or not _annual_owner_scope(data, before, local if absolute else ''):
        return None
    if absolute and _target_revenue_scope(data, absolute['owner'] or '', ''):
        # Sentence/semicolon boundaries after an actual amount terminate its
        # period. A preceding amountless Q2/year preamble never reaches here.
        if re.search(r'[。；;\n]', before[amounts[-1].end():]):
            return local
    if relative:
        previous = amounts[-1]
        left = max(before.rfind(mark, 0, previous.start()) for mark in ('。', '；', ';', '\n')) + 1
        prior = before[left:previous.start()]
        periods = list(_PERIOD.finditer(prior))
        if (len(periods) == 1 and re.fullmatch(r'20\d{2}年?', re.sub(r'\s+', '', periods[0][0]))
                and '年度' in prior and _target_revenue_scope(data, prior, '')):
            return periods[0][0]
    return None


def local_annual_suffix_matches(claim: dict, data: dict) -> bool:
    """New presentation bindings consume the complete same-sentence qualifier."""
    from financial_money_claims import _PERIOD
    prefix = str(claim.get('financial_period_text') or '')
    cleaned = clean_observed_prefix(prefix, data)
    annual = completed_annual_clause(data, cleaned)
    if cleaned == prefix and annual is None and not claim.get('financial_observed_quote'):
        return True
    periods = list(_PERIOD.finditer(annual or cleaned))
    if len(periods) != 1 or not re.fullmatch(r'20\d{2}年?', re.sub(r'\s+', '', periods[0][0])):
        return True  # Dated official TTM and monthly scopes keep their own gates.
    suffix = str(claim.get('financial_amount_suffix') or '')
    return bool(re.fullmatch(
        r'\s*(?:[）)]|[（(]\s*來源\s*[:：]\s*data\.history\.rows(?:\[\d+\])?\s*[）)]'
        r'(?:僅為已觀測之銷售基準(?:[，,]並非市場規模定義)?)?)?\s*'
        r'(?:[，,]\s*(?:DCF\s*(?:狀態\s*(?:標示\s*)?為\s*)?unavailable'
        r'|換算\s*FCF\s*轉換率為\s*[+-]?\d+(?:\.\d+)?\s*%'
        r'|FCF\s*轉換率\s*[（(]\s*FCF\s*/\s*淨利\s*[）)]\s*為\s*[+-]?\d+(?:\.\d+)?\s*%'
        r'|顯示現金流(?:狀況)?隨(?:年度)?資本支出與營運資金變動而有(?:顯著)?波動))?\s*',
        suffix, re.I))


_NUMBER = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
_UNIT = r'(?:十億元?|百萬元?|億元?|萬元?|元|TWD|billion|million)'
_CAGR_ENDPOINTS = re.compile(
    r'(?P<first_year>20\d{2})\s*(?:年)?\s*(?:至|到|-)\s*(?P<last_year>20\d{2})\s*年'
    r'(?:之\s*\d+\s*年)?\s*營收\s*CAGR\s*(?:達|為)\s*' + _NUMBER + r'%\s*[，,]\s*'
    r'(?P<metric>營收)\s*(?:從|自|由)\s*(?P<first>' + _NUMBER + r')\s*(?P<first_unit>' + _UNIT + r')\s*'
    r'(?:成長|增加|提升|下降|減少|下滑)?(?:至|到)\s*(?P<last>' + _NUMBER + r')\s*(?P<last_unit>' + _UNIT + r')', re.I)
_MONTH_COMPARISON = re.compile(
    r'(?P<year>20\d{2})\s*年\s*(?P<month>1[0-2]|0?[1-9])\s*月\s*'
    r'(?P<metric>營收)\s*(?:為|達|約為|約)?\s*(?P<first>' + _NUMBER + r')\s*(?P<first_unit>' + _UNIT + r')'
    r'(?P<comparison>(?:\s*雖(?:高於|低於)\s*(?:(?P<second_year>20\d{2})\s*年)?'
    r'(?P<second_month>1[0-2]|0?[1-9])\s*月\s*之?\s*(?P<second>' + _NUMBER + r')\s*(?P<second_unit>' + _UNIT + r')'
    r'|\s*雖較\s*(?P<qualitative_month>1[0-2]|0?[1-9])\s*月\s*(?:回升|下降))'
    r'\s*[，,]\s*(?:但)?仍(?:低於|高於|未突破)\s*(?:(?P<last_year>20\d{2})\s*年)?'
    r'(?P<last_month>1[0-2]|0?[1-9])\s*月\s*之?\s*(?P<last>' + _NUMBER + r')\s*(?P<last_unit>' + _UNIT + r')(?:的高點)?)', re.I)
_PRECEDING_CAGR = re.compile(
    r'^\s*(?:[-*]\s*)?(?:短期營收動能波動\s*[:：]\s*)?雖然\s*'
    r'(?P<owner>.*?)20\d{2}\s*(?:年)?\s*(?:至|到|-)\s*20\d{2}\s*年\s*營收\s*CAGR\s*(?:達|為)\s*'
    + _NUMBER + r'%\s*[，,]\s*但\s*$', re.I)


def extract_local_comparisons(markdown: str, existing: list[dict]) -> list[dict]:
    """Bind only complete observed comparison grammars; keep every amount.

    Values still go through the normal source checker. A trailing scope label,
    peer subject, ambiguous cross-year shorthand or future statement cannot
    gain evidence from this presentation adapter.
    """
    import math
    from financial_claim_context import sentence_span
    result = list(existing)
    for line_number, raw in enumerate(str(markdown or '').splitlines(), 1):
        line = re.sub(r'[*`]', '', raw).replace('−', '-')
        for pattern, kind in ((_CAGR_ENDPOINTS, 'cagr_endpoints'), (_MONTH_COMPARISON, 'monthly_comparison')):
            for match in pattern.finditer(line):
                left, right = sentence_span(line, *match.span())
                prefix = line[left:match.start('metric')]
                templates = [c for c in result if c.get('line_number') == line_number
                             and c.get('financial_metric') == '營收'
                             and c.get('financial_period_text') == prefix
                             and c.get('reported_value') == float(match['first'].replace(',', ''))]
                if len(templates) != 1:
                    continue
                template = templates[0]
                owner = line[left:match.start()]
                if preceding := _PRECEDING_CAGR.fullmatch(owner):
                    owner = preceding['owner']
                suffix = line[match.end():right]
                bound = not suffix.strip()  # Unparsed qualifiers remain unresolved.
                if kind == 'cagr_endpoints':
                    bound = bound and int(match['first_year']) < int(match['last_year'])
                    values = [('first', match['first_year'] + '年'), ('last', match['last_year'] + '年')]
                else:
                    year, month = int(match['year']), int(match['month'])
                    values = [('first', f'{year}年{month}月')]
                    for field in ('second', 'last'):
                        if match[field] is None:
                            continue
                        explicit_year = match[field + '_year']
                        compared_month = int(match[field + '_month'])
                        if not explicit_year and compared_month > month:
                            bound = False  # Do not invent a preceding calendar year.
                        values.append((field, f'{explicit_year or year}年{compared_month}月'))
                    if match['qualitative_month'] and int(match['qualitative_month']) > month:
                        bound = False
                additions = []
                for field, period in values:
                    number = match[field]; value = float(number.replace(',', ''))
                    invalid = len(number) > 64 or not math.isfinite(value)
                    additions.append({**template, 'reported_value': None if invalid else value,
                        'unit': match[field + '_unit'], 'financial_period_text': owner + period,
                        'financial_owner_text': owner, 'financial_amount_suffix': suffix,
                        'financial_scope_unbound': not bound or invalid,
                        'financial_display_precision': len(number.partition('.')[2]),
                        'financial_comparison': kind, 'financial_comparison_owner': owner,
                        'financial_comparison_owner_context': line[left:match.start()],
                        **({'financial_series_invalid_number': 'non_finite_or_long_numeric_token',
                            'financial_series_amount_text': number} if invalid else {})})
                result = [c for c in result if c is not template]
                result.extend(additions)
    result = _parenthesized_annual_fcf(result)
    return [{**claim, 'id': index + 1} for index, claim in enumerate(result)]


def _parenthesized_annual_fcf(claims: list[dict]) -> list[dict]:
    """Localize an observed annual FCF parenthesis, retaining all qualifiers.

    This changes neither amount nor sign. Source comparison still uses the
    saved year's typed history; the preceding TTM cannot supply its value.
    """
    result = []
    for claim in claims:
        prefix = str(claim.get('financial_period_text') or '')
        original_local = re.split(r'[。；;\n]', prefix)[-1]
        local = _LABEL.sub('', original_local)
        match = re.fullmatch(r'\s*(?P<owner>.*?)(?P<year>20\d{2})\s*年度\s*曾短暫實現\s*',
                             local)
        direction = re.fullmatch(re.escape(local.rstrip())
                                 + r'\s*(?P<direction>正值|負值)\s*[（(]\s*[）)]\s*',
                                 _LABEL.sub('', str(claim.get('financial_owner_text') or '')))
        if claim.get('financial_metric') not in {'FCF', '自由現金流'} or not match or not direction:
            result.append(claim)
            continue
        result.append({**claim,
            'financial_period_text': match['owner'] + match['year'] + '年度',
            'financial_owner_text': match['owner'],
            'financial_comparison': 'parenthesized_annual_fcf',
            'financial_comparison_owner': match['owner'],
            'financial_comparison_owner_context': prefix[:-len(original_local)] if original_local else prefix,
            'financial_parenthesized_annual_original_prefix': prefix,
            'financial_parenthesized_annual_direction': direction['direction']})
    return result


def _parenthesized_annual_owner_matches(claim: dict, data: dict) -> bool:
    """A closed parenthesis cannot hide a peer, currency, period or direction."""
    from financial_money_claims import _AMOUNT, _FOREIGN, _PERIOD, _annual_owner_scope, _finite, _target_revenue_scope
    owner = str(claim.get('financial_comparison_owner') or '')
    heading = str(claim.get('financial_heading') or '')
    before = str(claim.get('financial_comparison_owner_context') or '')
    parent = str(claim.get('financial_parent_context') or '')
    suffix = str(claim.get('financial_amount_suffix') or '')
    if (_FOREIGN.search(owner + heading + before + parent + suffix)
            or _CONSOLIDATED.search(owner + heading + before + parent + suffix)
            or _PERIOD.search(owner)):
        return False
    if not _target_revenue_scope(data, owner, heading):
        return False
    title = re.sub(r'^\s*#{1,6}\s*(?:[一二三四五六七八九十\d]+[、.]\s*)?', '', heading)
    title = re.sub(r'證據時點與來源|自由現金流分析|財務分析', '', title)
    if not _target_revenue_scope(data, title, ''):
        return False
    # A completed earlier amount ends its period, but never its issuer. Only
    # the earlier statement's official/individual labels are presentation here;
    # they are not applied to the new annual snapshot claim.
    if before.strip():
        if not _AMOUNT.search(before):
            return False
        prior = clean_observed_prefix(before, data)
        prior = re.sub(r'官方\s*個別\s*財報', '財報', prior)
        prior = re.sub(r'TTM\s*[（(]\s*20\d{2}-\d{2}-\d{2}\s*至\s*'
                       r'20\d{2}-\d{2}-\d{2}\s*[）)]', 'TTM', prior, flags=re.I)
        if not _annual_owner_scope(data, prior, owner):
            return False
    tail = re.fullmatch(
        r'\s*[）)]\s*(?:[，,]\s*但\s*(?P<year>20\d{2})\s*年度\s*與\s*最新\s*TTM\s*均轉為負值'
        r'(?:\s*[，,]\s*顯示營運資金占用或資本支出壓力仍大)?)?\s*', suffix, re.I)
    if not tail:
        return False
    if tail['year']:
        # This tail only compares saved signs; it cannot establish an official
        # TTM period or attach that source scope to the annual snapshot.
        local_year = re.search(r'(20\d{2})年度$', str(claim.get('financial_period_text') or ''))
        years, history = data.get('years'), data.get('fcf_history')
        if (not local_year or tail['year'] == local_year[1]
                or not isinstance(years, list) or not isinstance(history, list)
                or len(years) != len(history)):
            return False
        positions = [i for i, year in enumerate(years) if str(year).strip() == tail['year']]
        if len(positions) != 1:
            return False
        annual, current = _finite(history[positions[0]]), _finite(data.get('free_cash_flow_raw'))
        if annual is None or current is None or annual >= 0 or current >= 0:
            return False
    value = claim.get('reported_value')
    direction = claim.get('financial_parenthesized_annual_direction')
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and ((direction == '正值' and value > 0) or (direction == '負值' and value < 0)))


def local_comparison_owner_matches(claim: dict, data: dict) -> bool:
    if not claim.get('financial_comparison'):
        return True
    if claim.get('financial_comparison') == 'parenthesized_annual_fcf':
        return _parenthesized_annual_owner_matches(claim, data)
    from financial_money_claims import _FOREIGN, _target_revenue_scope, _annual_owner_scope
    owner = str(claim.get('financial_comparison_owner') or '')
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    original = str(claim.get('financial_comparison_owner_context') or '')
    if _FOREIGN.search(owner + heading + parent + original) or _CONSOLIDATED.search(owner + heading + parent + original):
        return False
    if not _target_revenue_scope(data, owner, heading):
        return False
    if _target_revenue_scope(data, owner, heading, require_explicit=True):
        return True
    return _annual_owner_scope(data, parent, owner)
