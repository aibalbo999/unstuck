"""Match money claims by metric, explicit period, currency and named source.

These checks establish saved-snapshot consistency, never independent source
truth, source availability at publication, or a valuation/order permission.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from financial_local_amounts import observed_quote_heading, amount_sentence_span

from financial_claim_context import (
    sentence_span, is_actual_claim, PROJECTION as _HEADING_PROJECTION,
    THRESHOLD as _HEADING_THRESHOLD, CONDITIONAL as _HEADING_CONDITIONAL,
)
from financial_money_claims import (
    _AMOUNT, _CHANGE_AMOUNT, _ERROR_EXAMPLE, _FOREIGN, _NON_AMOUNT, _NON_ACTUAL,
    _PARTIAL_YEAR, _PERIOD, _SCALES, _finite, _source,
    financial_period_scope, is_unit_definition_number, signed_amount_number,
    revenue_segment_scope,
)

_METRIC = re.compile(r'自由現金流|(?<![A-Za-z])FCF(?![A-Za-z])|free[_ ]cash[_ ]flow|營業收入|營收|revenue|稅後淨利|淨利|net[_ ]income', re.I)
_VALUE = re.compile(r'^\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)(?![A-Za-z])', re.I)
_YEAR_HEADER = re.compile(r'^(?:期間|年度|年份|年分|year|period)$', re.I)
_UNBOUND_SCOPE = re.compile(r'平均(?:每)?(?:個)?月|每月平均|月均|單月|月度|季度|單季|monthly|quarterly|per\s*month',re.I)
_PROJECTION = re.compile(r'情境|假設|預估|預測|目標|forecast|project(?:ed|ion)|estimate(?:d)?|scenario|assumption',re.I)
_CURRENCY_DECLARATION = re.compile(r'(?:單位|幣別|currency|denominated)\s*(?:為|是|[:：]|in)?\s*(?:美元|美金|USD|US\$|EUR|歐元|人民幣|CNY|RMB|JPY|日圓|HKD|港幣)',re.I)
_POSTFIX = re.compile(r'(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<unit>十億元?|billion|百萬元?|million|億元?|萬元?|B|元|TWD)(?:_twd)?\s*(?:的)?(?:年度|全年)?(?P<metric>自由現金流|FCF|營業收入|營收|稅後淨利|淨利)(?!率)',re.I)
_MONTH = re.compile(r'(20\d{2})年(1[0-2]|0?[1-9])月')
_MONTH_ROW = re.compile(r'(20\d{2})年(1[0-2]|0?[1-9])月: NT\$(?P<amount>[+-]?\d+(?:\.\d+)?)億')
_MONTH_SCOPE_UNBOUND = re.compile(r'平均|月均|每月|季度|單季|全年|年度|年化|annual|quarter|per\s*month|從|由|分別|依序|各為|至|(?<!達)到|區間|~|～', re.I)
_CAPEX_AMOUNT = re.compile(
    r'(?P<metric>(?:CapEx|資本支出)(?:\s*[（(][^）)\n]{1,60}[）)])?'
    r'|PPE購置支出|購置不動產(?:、|及|與|\s)*廠房(?:、|及|與|\s)*設備'
    r'|(?:加上|含)無形(?:資產)?(?:購置)?(?:合計)?)'
    r'(?P<link>\s*(?:(?:約為?|為|現金流入|現金流出|支出|並非|不是)\s*)*)'
    r'(?P<number>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*'
    r'(?P<unit>(?:十億|百萬|億|萬)?(?:美元|美金|港元|港幣|日圓|日元|歐元|人民幣|元)|billion|million|TWD)', re.I)


def _capex_amount_claims(line, raw, line_number, heading):
    """Keep explicit purchase components; bare CapEx still counts as unknown."""
    claims = []; previous = None
    for match in _CAPEX_AMOUNT.finditer(line):
        left, right = sentence_span(line, *match.span())
        prefix = line[left:match.start()]
        metric = re.sub(r'\s+', '', match['metric'])
        continuation = bool(re.fullmatch(r'(?:加上|含)無形(?:資產)?(?:購置)?(?:合計)?', metric))
        ppe = r'購置不動產(?:、|及|與)*廠房(?:、|及|與)*設備'
        definition = ('ppe_and_intangible_purchase' if re.fullmatch(
            r'(?:CapEx|資本支出)[（(](?:PPE(?:及|與|含)無形資產|含無形資產)[）)]', metric, re.I)
            else 'ppe_purchase' if re.fullmatch(
            r'(?:CapEx|資本支出)[（(](?:PPE|' + ppe + r')[）)]|PPE購置支出|' + ppe, metric, re.I)
            else '')
        if continuation and previous and previous[0].end() >= left:
            old_match, old_claim = previous
            if (old_claim['financial_capex_definition'] == 'ppe_purchase'
                    and re.fullmatch(r'\s*[，,、]\s*', line[old_match.end():match.start()])):
                definition = 'ppe_and_intangible_purchase'
                prefix = old_claim['financial_period_text']
        claim = _money_claim('CapEx', match['number'], match['unit'], line_number, raw, prefix,
            actual=is_actual_claim(line, *match.span()) and not _NON_ACTUAL.search(match['link'])
            and not any(pattern.search(heading) for pattern in (_HEADING_PROJECTION, _HEADING_CONDITIONAL, _HEADING_THRESHOLD)))
        claim.update(financial_capex=True, financial_capex_definition=definition,
            financial_heading=heading, financial_owner_text=prefix,
            financial_capex_link=match['link'], financial_amount_suffix=line[match.end():right])
        claims.append(claim); previous = (match, claim)
    return claims


def _explicit_month(prefix):
    periods = list(_PERIOD.finditer(prefix))
    if len(periods) != 1 or _PARTIAL_YEAR.search(prefix):
        return None
    match = _MONTH.fullmatch(re.sub(r'\s+', '', periods[0].group()))
    return (int(match[1]), int(match[2])) if match else None


def _amount_scope_unbound(prefix, link, suffix):
    scope = prefix[-20:] + link + suffix
    if _explicit_month(prefix):
        # A directional verb ending at one explicit month's amount is not a
        # multi-period range. Keep bare 至 and all period/range markers blocked.
        scope = re.sub(r'(?:亦)?(?:回落|上升|下降)至', '', scope)
        return bool(_PARTIAL_YEAR.search(scope) or _MONTH_SCOPE_UNBOUND.search(scope)
                    or _PERIOD.search(link + suffix))
    return bool(_UNBOUND_SCOPE.search(scope) or re.search(r'從|由|分別|依序|各為', link))


def _metric(text):
    match = _METRIC.search(text)
    if not match:
        return None
    name=match.group().upper().replace('_',' ')
    return {'FREE CASH FLOW':'FCF','REVENUE':'營收','NET INCOME':'淨利'}.get(name,name)


def _money_claim(metric, number, unit, line_number, line, period_text, *, actual=True):
    return {'label': metric, 'reported_value': float(number.replace(',', '')),
            'unit': unit, 'claim_type': 'financial', 'financial_amount': True,
            'financial_metric': metric, 'financial_period_text': period_text,
            'financial_display_precision': len(number.partition('.')[2]),
            'financial_actual': actual, 'line_number': line_number, 'raw_text': line}


def extract_financial_amounts(markdown: str, existing: list[dict]) -> list[dict]:
    """Keep real amounts, replacing a table period token with its amount cell."""
    additions = []; period_tokens = set(); seen = set(); headers = []; headings_by_line = {}; parents_by_line = {}
    in_code = False; heading = ''; projected_lines=set(); paragraph = ''; list_scopes = []
    heading_stack = []; ancestors_by_line = {}
    for line_number, raw in enumerate(markdown.splitlines(), 1):
        if raw.strip().startswith('```'):
            in_code = not in_code
            paragraph = ''
            list_scopes = []
            continue
        if in_code:
            continue
        line = re.sub(r'[*`]', '', raw).replace('−', '-')
        # Parenthesized synonyms denote one metric, not a second metric with
        # an owner made from the first metric's name.
        line = re.sub(r'自由現金流\s*[（(]\s*FCF\s*[）)]', '自由現金流', line, flags=re.I)
        # A dated FCF annotation between the metric and amount must not make
        # the amount disappear. Move only this bounded annotation for parsing;
        # raw_text remains the exact original line and source gates still apply.
        line = re.sub(r'(?P<metric>自由現金流|(?<![A-Za-z])FCF(?![A-Za-z]))\s*'
                      r'(?P<period>[（(]\s*(?:至|截至)\s*20\d{2}-\d{2}-\d{2}\s*[）)])',
                      lambda m: m['period'] + m['metric'], line, flags=re.I)
        if not line.strip() or line.lstrip().startswith(('#', '|')):
            paragraph = ''
            list_scopes = []
        elif re.match(r'^\s*(?:[-+*]|\d+[.)])\s+', raw):
            # Sibling list items do not share financial amounts or subjects;
            # a prose introduction still scopes every item in that list.
            expanded = raw.expandtabs(4)
            indent = len(expanded) - len(expanded.lstrip())
            while list_scopes and indent < list_scopes[-1][0]:
                list_scopes.pop()
            if list_scopes and indent == list_scopes[-1][0]:
                paragraph = list_scopes[-1][1]
            else:
                list_scopes.append((indent, paragraph))
        if line.lstrip().startswith('#'):
            heading=line
            marker = re.match(r'^\s*(#{1,6})(?!#)', line)
            if marker is not None:
                level = len(marker[1])
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, line))
        ancestors_by_line[line_number] = [text for _, text in heading_stack]
        headings_by_line[line_number]=heading
        parents_by_line[line_number]=paragraph
        quoted_observation = observed_quote_heading(heading, line)
        actual_heading = '' if quoted_observation else heading
        additions.extend(_capex_amount_claims(line, raw, line_number, actual_heading))
        projected_heading=bool(_PROJECTION.search(actual_heading))
        if projected_heading:
            projected_lines.add(line_number)
        if line.strip().startswith('|'):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            # Non-numeric TAM/SAM "未評估" rows are data, not new headers.
            if cells and any(_YEAR_HEADER.fullmatch(cell) for cell in cells) and not any(re.search(r'\d', cell) for cell in cells):
                headers = cells
            period_columns = [i for i,h in enumerate(headers) if _YEAR_HEADER.fullmatch(h)]
            periods = [(i,cell) for i,cell in enumerate(cells) if i in period_columns and re.fullmatch(r'20\d{2}年?|TTM|LTM',cell,re.I)]
            metrics = [_metric(cell) for cell in cells if _metric(cell)]
            if len(periods) == 1 and len(set(metrics)) == 1:
                _,period = periods[0]
                for cell in cells:
                    if match := _VALUE.match(cell):
                        table_claim=_money_claim(metrics[0],match[1],match[2],line_number,raw,period,actual=not projected_heading and not _PROJECTION.search(' '.join(cells)))
                        table_claim['financial_heading'] = heading
                        table_claim['financial_scope_unbound']=bool(_UNBOUND_SCOPE.search(' '.join(cells)))
                        table_claim['foreign_currency_declared']=bool(_FOREIGN.search(' '.join(cells)))
                        additions.append(table_claim)
                        if re.fullmatch(r'20\d{2}年?',period):
                            period_tokens.add((line_number,float(period.removesuffix('年'))))
        else:
            headers = []
        for match in _AMOUNT.finditer(line):
            if is_unit_definition_number(line, *match.span('number')):
                continue
            left,right=amount_sentence_span(line,*match.span()); prefix=line[left:match.start()]
            local_prefix=re.split(r'[，,、]|但是|然而|但',prefix)[-1]
            suffix=re.split(r'[，,、]|但是|然而|但',line[match.end():right],maxsplit=1)[0]
            if (_NON_AMOUNT.search(local_prefix+match['link'])
                    or re.match(r'\s*(?:%|股|/\s*股|倍)',line[match.end():])
                    or _CHANGE_AMOUNT.search(match['link'])
                    or _ERROR_EXAMPLE.search(local_prefix+suffix)):
                continue
            metric=match['metric'].upper(); number=signed_amount_number(match)
            # "年度營收與1.63 billion_twd的淨利" ties the amount to
            # the following metric, not the preceding coordinated noun.
            following_metric=re.match(r'(?:_twd)?\s*(?:的)?(?:年度|全年)?(自由現金流|FCF|營業收入|營收|稅後淨利|淨利)',line[match.end():],re.I)
            if following_metric and _metric(following_metric[1])!=metric:
                continue
            following_debt = re.match(r'\s*的\s*(有息負債|有息借款(?:含租賃)?)', line[match.end():])
            coordinated_debt = (following_debt is not None and metric in {'FCF', '自由現金流'}
                and re.fullmatch(r'\s*[與及和]\s*(?:近|約)?\s*', match['link']) is not None)
            if coordinated_debt:
                # The preceding FCF has its own postfix amount. Keep this
                # second amount under its explicit debt metric, never as FCF.
                # Its abbreviated period/owner remains unresolved.
                metric = following_debt[1]
            period_prefix = paragraph + line[:match.start()] if re.search(r'年度|全年', prefix) and not quoted_observation else prefix
            claim=_money_claim(metric,number,match['unit'],line_number,raw,period_prefix,actual=(not projected_heading or bool(re.search(r'即期\s*$', local_prefix))) and is_actual_claim(line,*match.span()) and not _PROJECTION.search(local_prefix+match['link']+suffix))
            claim['financial_heading']=heading
            if quoted_observation:
                claim['financial_observed_quote'] = True
            claim['financial_owner_text']=prefix+match['link']+suffix
            claim['financial_amount_suffix']=line[match.end():right]
            claim['financial_scope_unbound']=coordinated_debt or _amount_scope_unbound(prefix,match['link'],suffix)
            claim['foreign_currency_declared']=bool(_FOREIGN.search(local_prefix+match['link']+suffix) or _CURRENCY_DECLARATION.search(line[match.end():right]))
            additions.append(claim)
        for match in _POSTFIX.finditer(line):
            left,right=amount_sentence_span(line,*match.span());prefix=line[left:match.start()]
            suffix=line[match.end():right]
            if _ERROR_EXAMPLE.search(prefix) or _NON_AMOUNT.search(prefix[-12:]):
                continue
            number = match['number']; sign_ambiguous = False
            negative_word = re.search(r'負\s*$', prefix)
            if negative_word is not None:
                sign_ambiguous = (number.startswith(('-', '+')) or re.search(
                    r'(?:並非|不是|不為|不|非|未|無法|否認)\s*負\s*$', prefix) is not None)
                if not sign_ambiguous:
                    number = '-' + number
                    # This local unary sign belongs to the amount, not its
                    # issuer/year prefix. Original raw text remains intact.
                    prefix = prefix[:negative_word.start()]
            period_prefix = paragraph + line[:match.start()] if re.search(r'年度|全年', prefix) else prefix
            if negative_word is not None and not sign_ambiguous and re.search(r'年度|全年', prefix):
                period_prefix = paragraph + line[:left] + prefix
            claim=_money_claim(_metric(match['metric']),number,match['unit'],line_number,raw,period_prefix,
                               actual=not sign_ambiguous and not projected_heading and is_actual_claim(line,*match.span()) and not _PROJECTION.search(prefix[-30:]+match.group()+suffix))
            claim['financial_heading']=heading
            claim['financial_amount_suffix']=suffix
            if _explicit_month(prefix):
                monthly_suffix=re.split(r'[，,、]|但是|然而|但',suffix,maxsplit=1)[0]
                claim['financial_owner_text']=prefix+monthly_suffix
                claim['financial_scope_unbound']=_amount_scope_unbound(prefix,line[match.end('unit'):match.end()],monthly_suffix)
            else:
                claim['financial_scope_unbound']=bool(_UNBOUND_SCOPE.search(prefix[-20:]+match.group()+suffix) or re.search(r'(?:至|到|～|~|區間|每(?:賺進|賺取|獲得|產生|賺)?)\s*$',prefix))
            claim['foreign_currency_declared']=bool(_FOREIGN.search(prefix[-20:]+match.group()+suffix) or _CURRENCY_DECLARATION.search(suffix))
            additions.append(claim)
        if line.strip() and not line.lstrip().startswith(('#', '|')):
            paragraph += line + '\n'
    unique=[]
    for claim in additions:
        key=(claim['line_number'],claim['financial_metric'],claim['reported_value'],claim['unit'].lower(),claim['financial_period_text'],claim.get('financial_capex_definition'))
        if key not in seen:
            unique.append(claim);seen.add(key)
    result=[]
    for claim in existing:
        if any(a.get('financial_capex') and a['line_number'] == claim['line_number']
               and a['reported_value'] == claim['reported_value']
               and re.search(r'CapEx|資本支出|PPE|購置|無形', str(claim.get('label') or ''), re.I)
               for a in unique):
            continue
        if (claim['line_number'],claim['reported_value']) in period_tokens and not claim.get('unit') and _metric(str(claim.get('label') or '')):
            continue
        if any(a['line_number']==claim['line_number'] and a['reported_value']==claim['reported_value'] and a['unit'].lower()==str(claim.get('unit') or '').lower() and _metric(str(claim.get('label') or ''))==a['financial_metric'] for a in unique):
            continue
        # Even a labelled FCF number without a period/unit may not cherry-pick
        # an arbitrary old positive history as the current cash-flow fact.
        if re.fullmatch(r'(?:FCF|自由現金流|free[_ ]?cash[_ ]?flow)',str(claim.get('label') or ''),re.I):
            claim={**claim,'financial_amount':True,'financial_metric':'FCF','financial_period_text':'','financial_actual':True}
        metric=_metric(str(claim.get('label') or ''))
        unit=str(claim.get('unit') or '').lower()
        label=str(claim.get('label') or '')
        if (metric in {'FCF', '自由現金流'} and not unit
                and re.search(r'年度|全年|20\d{2}', label)
                and not _NON_AMOUNT.search(label)):
            # A generic labelled annual amount with no bound unit cannot use
            # the latest FCF scalar. Preserve the original claim/denominator;
            # do not infer a scale or borrow a period from a neighbouring item.
            claim={**claim,'financial_amount':True,'financial_metric':metric,
                   'financial_period_text':label,'financial_scope_unbound':True,
                   'financial_actual':claim['line_number'] not in projected_lines
                   and not bool(_PROJECTION.search(str(claim.get('raw_text') or '')))}
        if metric and unit in _SCALES and not re.match(r'^\s*\|\s*[*_`]*最終投資建議',str(claim.get('raw_text') or '')):
            label=str(claim.get('label') or '')
            period_text=label
            if not _PERIOD.search(label):
                text=str(claim.get('raw_text') or '')
                found=_METRIC.search(text)
                if found:
                    period_text=text[:found.start()]
            claim={**claim,'financial_amount':True,'financial_metric':metric,
                   'financial_period_text':period_text,
                   'financial_heading':headings_by_line.get(claim['line_number'],''),
                   'financial_actual':claim['line_number'] not in projected_lines and not bool(_PROJECTION.search(str(claim.get('raw_text') or ''))),
                   'financial_scope_unbound':bool(_UNBOUND_SCOPE.search(str(claim.get('raw_text') or ''))),
                   'foreign_currency_declared':bool(_FOREIGN.search(str(claim.get('raw_text') or '')))}
        result.append(claim)
    result.extend(unique)
    for claim in result:
        if claim.get('financial_amount') and claim['line_number'] in ancestors_by_line:
            claim['_financial_heading_ancestors'] = list(ancestors_by_line[claim['line_number']])
        if heading := headings_by_line.get(claim['line_number']):
            claim.setdefault('financial_heading', heading)
        if parent := parents_by_line.get(claim['line_number']):
            claim['financial_parent_context'] = parent
    from evidence_financial_series import extract_financial_series
    from financial_local_amounts import extract_local_comparisons
    return extract_local_comparisons(markdown, extract_financial_series(markdown, result))


def _immediate_fcf_reference(data, prefix, heading):
    """An explicit current input is an arithmetic reference, never a dated fact."""
    from financial_money_claims import _target_revenue_scope
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    marker = re.search(r'即期\s*$', local)
    if (marker is None or _PERIOD.search(local + heading)
            or re.search(r'年度|全年', local + heading)
            or _PARTIAL_YEAR.search(local) or _FOREIGN.search(prefix + heading)
            or str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}):
        return None
    owner = re.sub(r'^\s*(?:且|並且|而|同時)\s*', '', local[:marker.start()])
    owner = re.sub(r'^\s*(?:[-*]|\d+[.)])?\s*', '', owner)
    owner = re.sub(r'^(?:(?:現金流壓力|現金流與流動性風險|產能與\s*CapEx\s*壓力|成長分析引文)\s*[:：]\s*)+', '', owner, flags=re.I)
    if not _target_revenue_scope(data, owner, heading):
        return None
    before = prefix[:len(prefix) - len(local)]
    for clause in reversed(re.split(r'[，,、。；;\n]|但是|然而|但', before)):
        if _METRIC.search(clause) and (_AMOUNT.search(clause) or re.search(r'[+-]?\d+(?:\.\d+)?\s*%', clause)):
            break  # An earlier amount/ratio owns its period; a preamble does not.
        if _PERIOD.search(clause) or re.search(r'年度|全年', clause):
            return None
    if not _target_revenue_scope(data, owner, heading, require_explicit=True):
        for clause in reversed(re.split(r'[，,、。；;\n]|但是|然而|但', before)):
            metric = _METRIC.search(clause)
            if metric:
                prior_owner = clause[:metric.start()]
                if not _target_revenue_scope(data, prior_owner, heading):
                    return None
                if _target_revenue_scope(data, prior_owner, heading, require_explicit=True):
                    break
                continue  # An implicit ratio does not reset an earlier issuer.
            if clause.strip():
                return None  # Keep an earlier owner, currency or period preamble unresolved.
    raw = _finite(data.get('free_cash_flow_raw'))
    return (raw, 'data.free_cash_flow_raw', raw, 'twd', '即期輸入（期間未核實）') if raw is not None else None


def _financial_source(data,metric,prefix,heading='',owner_text=None):
    from financial_money_claims import other_financial_owner
    if other_financial_owner(data, prefix, heading):
        return None
    local = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    if metric in {'FCF', '自由現金流'} and '即期' in local:
        # Even an unresolved current claim must not fall through to the year of
        # a preceding annual ratio and borrow its annual FCF history.
        return _immediate_fcf_reference(data, prefix, heading)
    prefix = financial_period_scope(data, prefix)
    if prefix is None:
        return None
    if metric in {'營收', '營業收入'} and _explicit_month(prefix):
        return _monthly_source(data, prefix, heading, owner_text)
    source=_source(data,metric,prefix)
    if source is not None:
        return source
    if str(data.get('financial_currency') or '').upper() not in {'TWD','NTD'} or _PARTIAL_YEAR.search(prefix):
        return None
    periods=list(_PERIOD.finditer(prefix))
    if periods and all(p.group().upper() == 'TTM' for p in periods):
        # Repeated explicit TTM labels in coordinated clauses are the same
        # declared period, not two incompatible years. No dated term is erased.
        prefix = _PERIOD.sub('', prefix, count=len(periods)-1) if len(periods)>1 else prefix
        periods=list(_PERIOD.finditer(prefix))
    repeated_annual_fcf = (metric in {'FCF', '自由現金流'} and len(periods) > 1
        and all(re.fullmatch(r'20\d{2}年?', re.sub(r'\s+', '', p.group())) for p in periods)
        and len({re.sub(r'\s+|年', '', p.group()) for p in periods}) == 1
        and not any(re.fullmatch(r'\s*[年至到~～–—-]+\s*', prefix[a.end():b.start()])
                    for a, b in zip(periods, periods[1:])))
    if len(periods)!=1 and not repeated_annual_fcf:
        return None
    period=re.sub(r'\s+','',periods[0].group()).upper()
    if metric in {'FCF','自由現金流'} and re.fullmatch(r'20\d{2}年?',period):
        contract=data.get('unit_contract') or {}
        quant_contract=(data.get('quant_metrics') or {}).get('unit_contract') if isinstance(data.get('quant_metrics'),dict) else {}
        if any(isinstance(c,dict) and c.get('money','billion_twd')!='billion_twd' for c in (contract,quant_contract)):
            return None
        years=data.get('years');values=data.get('fcf_history');year=period.removesuffix('年')
        if not isinstance(years,list) or not isinstance(values,list) or len(years)!=len(values):
            return None
        indexes=[i for i,y in enumerate(years) if str(y)==year]
        if len(indexes)==1 and (raw:=_finite(values[indexes[0]])) is not None:
            return raw*1e9,f'data.fcf_history[{indexes[0]}]',raw,'billion_twd',year
    if period=='TTM' and metric in {'營收','營業收入','淨利','稅後淨利'}:
        # Named raw-TWD fields, not arbitrary untyped revenue objects.
        field='revenue_ttm_raw' if metric in {'營收','營業收入'} else 'net_income_ttm_raw'
        if (raw:=_finite(data.get(field))) is not None:
            return raw,f'data.{field}',raw,'twd','TTM'
    return None


def _monthly_source(data, prefix, heading, owner_text):
    """Read only the canonical formatted monthly series captured for this run.

    The preserved string has an explicit calendar month and NT$ scale. Matching
    it proves displayed snapshot consistency, not raw supplier precision or
    independent primary-source verification. Never search arbitrary strings.
    """
    if str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return None
    year, month = _explicit_month(prefix)
    from financial_money_claims import _target_revenue_scope
    from financial_local_amounts import clean_observed_prefix
    from source_content_selection import company_aliases
    owner = clean_observed_prefix(owner_text if isinstance(owner_text,str) else prefix, data)
    owner = re.sub(r'^\s*然而\s*[，,]\s*', '', owner)
    owner = _PERIOD.sub('', owner)
    # A provider-labelled growth ratio is not the issuer of the following dated
    # monthly amount. Only complete, known ratio clauses may be skipped; named
    # peers, foreign-currency declarations and free prose keep failing closed.
    pieces = re.split(r'[，,、]', owner)
    provider_ratio = r'(?:Yahoo\s*)?(?:即期|近期)?(?:獲利|營收)成長率(?:呈現|為)\s*[+-]?\d+(?:\.\d+)?%\s*(?:[（(]growth[）)])?'
    if len(pieces) > 1 and all(re.fullmatch(r'更警惕的是|' + provider_ratio, part.strip(), re.I) for part in pieces[:-1]):
        owner = pieces[-1]
    owner = re.sub(r'^\s*月(?=\s*(?:亦|回落|上升|下降|高達|達|僅|為|約))', '', owner)
    # Preserve target identity before removing amount modifiers (e.g. 達 in
    # 台達電/達方). The shared scope check still rejects any remaining issuer.
    for alias in sorted(company_aliases(data), key=len, reverse=True):
        pattern = (re.escape(alias) if re.search(r'[\u3400-\u9fff]', alias)
                   else r'(?<!\w)' + re.escape(alias) + r'(?!\w)')
        owner = re.sub(pattern, '本公司', owner, flags=re.I)
    owner = re.sub(r'^\s*(?:[-*]\s*)?(?:支持證據|證據比對|具體佐證)\s*[:：]\s*', '', owner)
    owner = re.sub(r'[（(]\s*recent_monthly_revenue_text\s*[）)]', '', owner)
    owner = re.sub(r'(?:亦)?(?:回落|上升|下降)至|月營收|營業收入|營收|單月|月度|高達|達到|約為|僅|達|約|為|負|NT\$|TWD', '', owner, flags=re.I)
    if not _target_revenue_scope(data, owner, heading):
        return None
    rows = data.get('recent_monthly_revenue')
    if not isinstance(rows, list) or len(rows) > 120:
        return None
    matches = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, str) or len(raw) > 100:
            continue
        row = _MONTH_ROW.fullmatch(raw)
        if row and (int(row[1]), int(row[2])) == (year, month):
            value = _finite(float(row['amount']))
            if value is None or _finite(value * 1e8) is None:
                return None
            matches.append((value * 1e8, f'data.recent_monthly_revenue[{i}]', raw,
                            'formatted_ntd_100million', f'{year:04d}-{month:02d}'))
    return matches[0] if len(matches) == 1 else None


def _check_monthly_envelope(claim, snapshot, result, data, scale):
    """Check containment in the frozen six-month sample, never latest/PIT.

    Bounds need not equal observed extrema. A wider reported envelope can be
    true, while a bound excluding a displayed observation is a mismatch.
    """
    rows = data.get('recent_monthly_revenue')
    if (str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}
            or claim.get('financial_range_count') != 6
            or not isinstance(rows, list) or len(rows) != 6):
        return result
    observations = []
    for index, raw in enumerate(rows):
        row = _MONTH_ROW.fullmatch(raw) if isinstance(raw, str) and len(raw) <= 100 else None
        if (row is None or int(row[1]) != claim.get('financial_range_year')
                or len(row['amount']) > 24):
            return result
        value = _finite(float(row['amount']))
        if value is None or _finite(value * 1e8) is None:
            return result
        observations.append((int(row[2]), Decimal(row['amount']) * Decimal('100000000'), index, raw))
    months = [row[0] for row in observations]
    if months != list(range(months[0], months[0] + 6)):
        return result
    side = claim.get('financial_range_side')
    if side not in {'lower', 'upper'}:
        return result
    selected = min(observations, key=lambda row: row[1]) if side == 'lower' else max(observations, key=lambda row: row[1])
    _, expected, index, raw = selected
    reported = Decimal(str(claim['reported_value']))
    precision = claim.get('financial_display_precision', 0)
    quantum = Decimal(1).scaleb(-precision)
    scaled = Decimal(str(scale))
    try:
        rounded = (expected / scaled).quantize(quantum, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return result
    contained = reported <= rounded if side == 'lower' else reported >= rounded
    conversion_matches = True
    primary = claim.get('financial_range_primary')
    if isinstance(primary, dict):
        unit = str(primary.get('unit') or '').lower()
        primary_scale = _SCALES.get(unit.removesuffix('元'), _SCALES.get(unit))
        if primary_scale is None:
            return result
        primary_amount = Decimal(str(primary['number']).replace(',', '')) * Decimal(str(primary_scale))
        try:
            converted = (primary_amount / scaled).quantize(quantum, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return result
        conversion_matches = reported == converted
    matched = contained and conversion_matches
    # A parenthetical conversion must agree with the stated primary bound.
    # The observed extreme remains separate evidence for window containment;
    # recommending that extreme as the alias would contradict a wider bound.
    comparison_expected = primary_amount if not conversion_matches else expected
    base_path = ('analysis_evidence.sections.analysis_input.data.' if
                 snapshot.get('_financial_source_context') == 'preserved_original_analysis_input' else 'data.')
    paths = [f'{base_path}recent_monthly_revenue[{row[2]}]' for row in observations]
    observed_months = [f"{claim['financial_range_year']}-{month:02d}" for month in months]
    return {**result, 'status': 'verified' if matched else 'mismatch',
            'verification_scope': 'snapshot_monthly_window_envelope_consistency',
            'verification_reason_code': ('monthly_range_conversion_mismatch' if not conversion_matches else
                                         'matched_monthly_window_bound' if contained else 'monthly_window_bound_excludes_observation'),
            'candidate_count': 6, 'matched_path': paths[index], 'matched_value': float(comparison_expected / scaled),
            'financial_period': observed_months[0] + '..' + observed_months[-1],
            'financial_currency': 'TWD', 'source_value': float(expected / Decimal('100000000')),
            'source_text': raw, 'source_unit': 'formatted_ntd_100million',
            'reported_value_raw_twd': float(reported * scaled), 'expected_value_raw_twd': float(comparison_expected),
            'financial_range_comparison_reference': ('reported_range_primary' if not conversion_matches else 'observed_window_extreme'),
            'financial_range_observed_extreme_raw_twd': float(expected),
            'financial_range_observation_paths': paths, 'financial_range_observed_months': observed_months,
            'financial_range_bound_contains_observations': contained,
            'financial_range_conversion_consistent': conversion_matches,
            'financial_latest_window_verified': False, 'historical_point_in_time_verified': False,
            'verification_data_source': snapshot.get('_financial_source_context', 'saved_snapshot'),
            'analysis_input_cutoff': snapshot.get('_financial_input_cutoff', '')}


def _native_mode_a_structural_headings(data):
    """Exact native renderer strings for this data, never issuer-text stripping."""
    from agent_catalog import AGENT_NAMES
    from company_display import company_display_name
    from pipeline_modes import get_pipeline_definition
    from reporting.markdown_renderer import _display_text
    definition = get_pipeline_definition('v1')
    ticker = _display_text(data.get('ticker', 'N/A'))
    name = _display_text(company_display_name(data, data.get('company_name', ticker)))
    headings = {f"# {ticker} {name} - {definition['report_title']}"}
    # This is the exact markdown_renderer / build_agent_sections wrapper.
    # A custom sequence or an extra scope qualifier is intentionally unknown.
    headings.update(f"## {index}. {AGENT_NAMES.get(agent, f'Agent {agent}')} (Agent {agent})"
                    for index, agent in enumerate(definition['agents'], 1))
    return headings


def _explicit_individual_ttm_presentation(claim, data, tolerance_pct):
    """Consume only a complete dated TWD clause with bounded structural labels.

    No value, source, reporting period or denominator is invented. The original
    qualified official checkers still replay the documents and compare amounts.
    Source/scalar preambles, foreign owners/currencies and unknown prose cannot
    be stripped into an apparently official observation.
    """
    metric = claim.get('financial_metric')
    if (metric not in {'FCF', '自由現金流', '淨利', '稅後淨利', 'CapEx'}
            or claim.get('financial_actual') is False or claim.get('financial_scope_unbound')
            or claim.get('foreign_currency_declared') or claim.get('unit') != '億元'):
        return None
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    neutral = (r'\s*#{1,6}\s*(?:(?:[一二三四五六七八九十]{1,3}|[1-9][0-9]?)[、.]\s*)?'
               r'(?:獲利趨勢深析|自由現金流分析|已觀測財務與歷史反證|企業體質總結|成長潛力總評|現金流與獲利品質分析|估值解讀與資料品質限制|估值解讀與資料品質警示|估值方法可用性與資料品質警示|折現現金流（DCF）估值解讀)\s*')
    native_headings = _native_mode_a_structural_headings(data)
    # The exact source-owned valuation wrapper carries no financial period.
    native_headings.add('# 1623.TW（大東電）投資銀行等級估值解讀報告')
    native_headings.add('## Round 2：財務與估值')
    def structural(text):
        return text in native_headings or re.fullmatch(neutral, text) is not None
    ancestors = claim.get('_financial_heading_ancestors')
    if (type(ancestors) is not list or len(ancestors) > 6
            or any(type(text) is not str for text in ancestors)
            or (heading and (not ancestors or ancestors[-1] != heading))
            or (not heading and ancestors)
            or any(not structural(text) for text in ancestors)
            or any(text.strip() and not structural(text) for text in (heading, parent))):
        return None
    from official_financial_projection import read_official_financial_projection
    projection = read_official_financial_projection(data)
    if projection is None:
        return None
    facts = projection['facts']
    if (facts.get('ticker') != '1623.TW' or facts.get('issuer_name') != '大東電業廠股份有限公司'
            or facts.get('currency') != 'TWD' or facts.get('report_scope') != 'individual'):
        return None
    raw = re.sub(r'[*`]', '', str(claim.get('raw_text') or ''))
    number = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    pattern = (r'\s*(?:[-*]\s*)?(?:(?P<label>自由現金流缺口|官方\s*TTM\s*淨利規模|資本支出狀況)\s*[:：]\s*)?'
               r'(?P<owner>大東電業廠股份有限公司|大東電|1623(?:\.TW)?)\s*官方\s*個別\s*(?:財報\s*)?TTM\s*'
               r'[（(]\s*(?P<start>20\d{2}-\d{2}-\d{2})\s*至\s*(?P<end>20\d{2}-\d{2}-\d{2})\s*[）)]\s*'
               r'(?P<metric>自由現金流|FCF|稅後淨利|淨利|CapEx[（(]PPE\s*及\s*無形資產取得支出[）)])\s*'
               r'為\s*(?P<number>' + number + r')\s*億元\s*(?P<currency>新[臺台]幣|TWD|NTD)\s*[。.]?\s*')
    match = re.fullmatch(pattern, raw, re.I)
    if match is None or (match['start'], match['end']) != (facts['period_start'], facts['period_end']):
        return None
    parsed_metric = ('CapEx' if re.match('CapEx', match['metric'], re.I) else match['metric'])
    families = {'FCF':'fcf', '自由現金流':'fcf', '淨利':'income', '稅後淨利':'income', 'CapEx':'capex'}
    if families.get(parsed_metric) != families[metric]:
        return None
    label = re.sub(r'\s+', '', match['label'] or '')
    labels = {'fcf':{'', '自由現金流缺口'}, 'income':{'', '官方TTM淨利規模'}, 'capex':{'', '資本支出狀況'}}
    if label not in labels[families[metric]]:
        return None
    literal = match['number'].replace(',', '')
    precision = len(literal.partition('.')[2])
    if (len(literal) > 64 or len(literal.lstrip('+-').partition('.')[0]) > 20 or precision > 20
            or type(claim.get('reported_value')) not in (int, float)):
        return None
    try:
        if Decimal(str(claim['reported_value'])) != Decimal(literal):
            return None
    except InvalidOperation:
        return None
    # This is a consumed presentation view, never a rewrite of the input claim.
    prefix = match['owner'] + '官方個別TTM(' + match['start'] + '至' + match['end'] + ')'
    bound = {**claim, 'financial_period_text':prefix, 'financial_heading':'', 'financial_parent_context':'',
             'financial_owner_text':prefix, 'financial_amount_suffix':'', 'financial_display_precision':precision}
    bound.pop('_financial_heading_ancestors', None)
    if families[metric] == 'capex':
        from evidence_official_financial_claims import official_capex_claim
        bound['financial_capex_definition'] = 'ppe_and_intangible_purchase'
        checked = official_capex_claim(bound, data, tolerance_pct=tolerance_pct)
    elif families[metric] == 'fcf':
        from evidence_official_financial_claims import official_fcf_claim
        checked = official_fcf_claim(bound, data, scale=1e8, tolerance_pct=tolerance_pct)
    else:
        from evidence_official_income_claims import official_income_claim
        bound['financial_amount_suffix'] = match['currency']
        checked = official_income_claim(bound, data, scale=1e8, tolerance_pct=tolerance_pct)
    if checked is None:
        return None
    return {**checked, 'financial_narrative_resolution':{
        'contract':'explicit-individual-ttm-presentation:v1', 'period_start':match['start'], 'period_end':match['end'],
        'currency':'TWD', 'report_scope':'individual', 'original_claim_unchanged':True,
        'structural_heading_consumed':bool(heading.strip()), 'structural_label_consumed':label,
        'value_and_documents_checked_by_native_official_checker':True}}


def check_financial_amount(claim: dict,snapshot: dict,tolerance_pct: float) -> dict | None:
    if not claim.get('financial_amount'):
        return None
    presentation_claim = claim
    claim = {key:value for key,value in claim.items() if key != '_financial_heading_ancestors'}
    public={k:v for k,v in claim.items() if k not in {'context_text','financial_period_text','financial_heading','financial_owner_text','financial_amount_suffix','financial_series_owner','financial_series_owner_context','financial_series_span','financial_series_paragraph','financial_series_inherited_scope','_price_history_months','_legacy_conclusion_context_missing','_technical_as_of','_technical_default_atr14'}}
    result={**public,'status':'unverifiable','verification_reason_code':'financial_period_currency_or_unit_unknown',
            'verification_scope':'snapshot_financial_amount_consistency','candidate_count':0,
            'matched_path':'','matched_value':None,'diff_pct':None,'independent_primary_source_verified':False}
    if not claim.get('financial_actual',True):
        return {**result,'verification_reason_code':'financial_projection_not_observed_fact'}
    prefix=str(claim.get('financial_period_text') or '')
    heading=str(claim.get('financial_heading') or '')
    data=snapshot.get('data');data=data if isinstance(data,dict) else {}
    from financial_local_amounts import local_comparison_owner_matches, empirical_comparison_heading, local_annual_suffix_matches
    if not local_comparison_owner_matches(claim, data):
        return result
    if not local_annual_suffix_matches(claim, data):
        return {**result, 'verification_reason_code': 'financial_annual_postfix_scope_unbound'}
    if claim.get('financial_observed_quote') and re.search(
            r'合併|集團|consolidated|group', prefix + str(claim.get('financial_owner_text') or '')
            + str(claim.get('financial_amount_suffix') or ''), re.I):
        return result
    if claim.get('financial_metric') in {'營收', '營業收入'} and revenue_segment_scope(
            prefix, heading, str(claim.get('financial_parent_context') or ''), data=data):
        if snapshot.get('_financial_source_context') != 'original_input_unavailable':
            from evidence_segment_financial_claims import official_segment_amount
            official_segment = official_segment_amount(claim, data, tolerance_pct=tolerance_pct)
            if official_segment is not None:
                return {**result, **official_segment}
        return {**result, 'verification_reason_code': 'financial_segment_revenue_scope_unbound'}
    empirical_comparison = claim.get('financial_comparison') and empirical_comparison_heading(heading)
    if _explicit_month(prefix) and not empirical_comparison and any(p.search(heading) for p in
            (_HEADING_PROJECTION, _HEADING_THRESHOLD, _HEADING_CONDITIONAL)):
        return {**result,'verification_reason_code':'financial_projection_not_observed_fact'}
    if claim.get('financial_scope_unbound'):
        return {**result,'verification_reason_code':'financial_amount_scope_unbound'}
    if snapshot.get('_financial_source_context')=='original_input_unavailable':
        return {**result,'verification_reason_code':'financial_original_input_unavailable'}
    presentation = _explicit_individual_ttm_presentation(presentation_claim, data, tolerance_pct)
    if presentation is not None:
        return {**result, **presentation}
    if claim.get('financial_capex'):
        from evidence_official_financial_claims import official_capex_claim
        official = official_capex_claim(claim, data, tolerance_pct=tolerance_pct)
        return {**result, **official} if official is not None else result
    from evidence_financial_series import financial_series_owner_matches
    if not financial_series_owner_matches(claim, data):
        return {**result, 'verification_reason_code': 'financial_amount_scope_unbound'}
    unit=str(claim.get('unit') or '').lower()
    scale=_SCALES.get(unit.removesuffix('元'),_SCALES.get(unit))
    if scale is None or claim.get('foreign_currency_declared'):
        return result
    annual_direction = None
    from financial_money_claims import _official_ttm_followed_by_annual_period
    if _official_ttm_followed_by_annual_period(data, prefix):
        # The new source-owned annual transition must consume its postfix as
        # well as its prefix. Unknown qualifiers cannot borrow issuer history.
        suffix = claim.get('financial_amount_suffix')
        qualification = re.fullmatch(
            r'\s*(?:[（(]\s*(?P<direction>淨流入|淨流出|金額為零)\s*[）)])?'
            r'(?:\s*[（(]轉換率\s*[+-]?\d+(?:\.\d+)?\s*%[）)])?'
            r'(?:\s*[，,]\s*確實顯示獲利未有效轉化為真實現金流)?\s*', suffix) if isinstance(suffix, str) else None
        if qualification is None:
            return {**result, 'verification_reason_code': 'financial_annual_postfix_scope_unbound'}
        annual_direction = qualification['direction']
    local_period = re.split(r'[，,、。；;\n]|但是|然而|但', prefix)[-1]
    if (claim.get('financial_metric') in {'FCF', '自由現金流'}
            and re.match(r'^\s*(?:且\s*)?(?:主因為|主因是)\s*', local_period)):
        # The newly admitted causal annual clause must not hide a different
        # owner/period/currency in an amount postfix. A following separately
        # dated financial amount owns its own scope and stays in the denominator.
        suffix = claim.get('financial_amount_suffix')
        parts = re.split(r'[，,]', suffix, maxsplit=1) if isinstance(suffix, str) else []
        qualification = re.fullmatch(
            r'\s*(?:[（(]\s*(?P<direction>淨流入|淨流出|金額為零)\s*[）)])?\s*', parts[0]) if parts else None
        next_clause = re.split(r'[，,]', parts[1], maxsplit=1)[0] if len(parts) == 2 else ''
        following = _AMOUNT.search(next_clause)
        next_period = re.fullmatch(
            r'\s*(?:(?:且|而|另外)\s*)?(?:最新\s*)?(?:官方\s*)?'
            r'(?:TTM|LTM|20\d{2}\s*年(?:度)?)'
            r'(?:\s*[（(]\s*(?:至|截至)\s*20\d{2}-\d{2}-\d{2}\s*[）)])?\s*',
            next_clause[:following.start()], re.I) if following else None
        if qualification is None or (len(parts) == 2 and next_period is None):
            return {**result, 'verification_reason_code': 'financial_annual_postfix_scope_unbound'}
        annual_direction = qualification['direction']
    if claim.get('financial_series') == 'monthly_range':
        return _check_monthly_envelope(claim, snapshot, result, data, scale)
    from evidence_official_income_claims import official_income_claim
    official_income = official_income_claim(presentation_claim, data, scale=scale, tolerance_pct=tolerance_pct)
    if official_income is not None:
        return {**result, **official_income}
    if (claim.get('financial_metric') in {'淨利', '稅後淨利'}
            and (re.search(r'官方\s*個別\s*(?:財務報表|財報|報表)?\s*(?:TWD|NTD|新[臺台]幣)?\s*TTM', prefix, re.I)
                 or re.search(r'[（(]\s*來源\s*[:：]\s*(?:data\.)?cash_flow\.official_income_facts'
                              r'(?:\.source_documents(?:\[(?:\*|[0-9]+)?\])?(?:\.url)?)?'
                              r'(?=\s|[，,）)])', str(claim.get('financial_amount_suffix') or '')))):
        # A declared official individual TTM source which failed strict
        # binding cannot borrow an undated vendor scalar as a comparator.
        # Keep the same claim and denominator, without certifying its amount.
        return {**result, 'verification_reason_code': 'official_income_scope_unbound_no_vendor_fallback'}
    from evidence_official_financial_claims import official_fcf_claim
    official = official_fcf_claim(claim, data, scale=scale, tolerance_pct=tolerance_pct,
                                  heading_ancestors=presentation_claim.get('_financial_heading_ancestors'))
    if official is not None:
        return {**result, **official}
    source=_financial_source(data,claim.get('financial_metric'),str(claim.get('financial_period_text') or ''),
                             str(claim.get('financial_heading') or ''),claim.get('financial_owner_text'))
    if source is None:
        return result
    expected,path,original,source_unit,period=source
    reported=float(claim['reported_value'])*scale
    diff=abs(reported-expected)/max(abs(expected),1)*100
    precision=claim.get('financial_display_precision',len(str(claim['reported_value']).partition('.')[2]))
    rounded=(Decimal(str(expected))/Decimal(str(scale))).quantize(Decimal(1).scaleb(-precision),rounding=ROUND_HALF_UP)
    rounding_match=rounded==Decimal(str(claim['reported_value']))
    # Zero/history rounding cannot turn an established negative fact positive.
    same_sign=reported*expected>=0
    matched=same_sign and (diff<=tolerance_pct or rounding_match)
    if snapshot.get('_financial_source_context')=='preserved_original_analysis_input':
        path=path.replace('data.','analysis_evidence.sections.analysis_input.data.',1)
    checked = {**result,'status':'verified' if matched else 'mismatch',
            'verification_reason_code':'matched_financial_metric_period_unit' if matched else 'financial_metric_period_unit_mismatch',
            'candidate_count':1,'matched_path':path,'matched_value':expected/scale,'diff_pct':round(diff,4),
            'financial_period':period,'financial_currency':'TWD','source_value':original,'source_unit':source_unit,
            'reported_value_raw_twd':reported,'expected_value_raw_twd':expected,
            'verification_data_source':snapshot.get('_financial_source_context','saved_snapshot'),
            'analysis_input_cutoff':snapshot.get('_financial_input_cutoff','')}
    if annual_direction is not None and annual_direction != ('淨流入' if expected > 0 else '淨流出' if expected < 0 else '金額為零'):
        checked.update(status='mismatch', verification_reason_code='financial_annual_direction_mismatch')
    if claim.get('financial_metric') in {'FCF', '自由現金流'} and period == '即期輸入（期間未核實）':
        # Qualification comes from the source, never from the author's TTM label.
        checked.update({
            'status': 'unverifiable' if matched else 'mismatch',
            'verification_reason_code': ('financial_arithmetic_consistent_period_unverified' if matched
                                         else 'financial_current_amount_mismatch_period_unverified'),
            'financial_arithmetic_consistent': matched,
            'financial_period_verified': False,
        })
    return checked


def financial_comparison_snapshot(snapshot: dict) -> dict:
    """Bind original prose to captured input; a refresh cannot rewrite its facts."""
    if 'analysis_evidence' in snapshot:
        from report_analysis_evidence import validate_analysis_evidence
        packet=validate_analysis_evidence(snapshot['analysis_evidence'])
        section=(packet.get('sections') or {}).get('analysis_input') or {}
        if packet.get('input_verification')=='hash_verified' and section.get('status')=='preserved' and isinstance(section.get('data'),dict):
            return {'data':section['data'],'_financial_source_context':'preserved_original_analysis_input',
                    '_financial_input_cutoff':packet.get('analysis_input_cutoff','')}
        return {'data':{},'_financial_source_context':'original_input_unavailable'}
    if snapshot.get('refreshed_without_analysis_rerun') or snapshot.get('snapshot_refreshed_at'):
        return {'data':{},'_financial_source_context':'original_input_unavailable'}
    return {'data':snapshot.get('data'),'_financial_source_context':'saved_snapshot'}
