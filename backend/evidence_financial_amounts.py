"""Match money claims by metric, explicit period, currency and named source.

These checks establish saved-snapshot consistency, never independent source
truth, source availability at publication, or a valuation/order permission.
"""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from financial_claim_context import (
    sentence_span, is_actual_claim, PROJECTION as _HEADING_PROJECTION,
    THRESHOLD as _HEADING_THRESHOLD, CONDITIONAL as _HEADING_CONDITIONAL,
)
from financial_money_claims import (
    _AMOUNT, _CHANGE_AMOUNT, _ERROR_EXAMPLE, _FOREIGN, _NON_AMOUNT,
    _PARTIAL_YEAR, _PERIOD, _SCALES, _finite, _source,
    is_unit_definition_number,
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


def _explicit_month(prefix):
    periods = list(_PERIOD.finditer(prefix))
    if len(periods) != 1 or _PARTIAL_YEAR.search(prefix):
        return None
    match = _MONTH.fullmatch(re.sub(r'\s+', '', periods[0].group()))
    return (int(match[1]), int(match[2])) if match else None


def _amount_scope_unbound(prefix, link, suffix):
    scope = prefix[-20:] + link + suffix
    if _explicit_month(prefix):
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
    additions = []; period_tokens = set(); seen = set(); headers = []; headings_by_line = {}
    in_code = False; heading = ''; projected_lines=set()
    for line_number, raw in enumerate(markdown.splitlines(), 1):
        if raw.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r'[*`]', '', raw).replace('−', '-')
        if line.lstrip().startswith('#'):
            heading=line
        headings_by_line[line_number]=heading
        projected_heading=bool(_PROJECTION.search(heading))
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
            left,right=sentence_span(line,*match.span()); prefix=line[left:match.start()]
            local_prefix=re.split(r'[，,、]|但是|然而|但',prefix)[-1]
            suffix=re.split(r'[，,、]|但是|然而|但',line[match.end():right],maxsplit=1)[0]
            if (_NON_AMOUNT.search(local_prefix+match['link'])
                    or re.match(r'\s*(?:%|股|/\s*股|倍)',line[match.end():])
                    or _CHANGE_AMOUNT.search(match['link'])
                    or _ERROR_EXAMPLE.search(local_prefix+suffix)):
                continue
            metric=match['metric'].upper(); number=match['number']
            # "年度營收與1.63 billion_twd的淨利" ties the amount to
            # the following metric, not the preceding coordinated noun.
            following_metric=re.match(r'(?:_twd)?\s*(?:的)?(?:年度|全年)?(自由現金流|FCF|營業收入|營收|稅後淨利|淨利)',line[match.end():],re.I)
            if following_metric and _metric(following_metric[1])!=metric:
                continue
            if '負' in match['link'] and not number.startswith(('-', '+')):
                number='-'+number
            claim=_money_claim(metric,number,match['unit'],line_number,raw,prefix,actual=not projected_heading and is_actual_claim(line,*match.span()) and not _PROJECTION.search(local_prefix+match['link']+suffix))
            claim['financial_heading']=heading
            claim['financial_owner_text']=prefix+match['link']+suffix
            claim['financial_scope_unbound']=_amount_scope_unbound(prefix,match['link'],suffix)
            claim['foreign_currency_declared']=bool(_FOREIGN.search(local_prefix+match['link']+suffix) or _CURRENCY_DECLARATION.search(line[match.end():right]))
            additions.append(claim)
        for match in _POSTFIX.finditer(line):
            left,right=sentence_span(line,*match.span());prefix=line[left:match.start()]
            suffix=line[match.end():right]
            if _ERROR_EXAMPLE.search(prefix) or _NON_AMOUNT.search(prefix[-12:]):
                continue
            claim=_money_claim(_metric(match['metric']),match['number'],match['unit'],line_number,raw,prefix,
                               actual=not projected_heading and is_actual_claim(line,*match.span()) and not _PROJECTION.search(prefix[-30:]+match.group()+suffix))
            claim['financial_heading']=heading
            if _explicit_month(prefix):
                monthly_suffix=re.split(r'[，,、]|但是|然而|但',suffix,maxsplit=1)[0]
                claim['financial_owner_text']=prefix+monthly_suffix
                claim['financial_scope_unbound']=_amount_scope_unbound(prefix,line[match.end('unit'):match.end()],monthly_suffix)
            else:
                claim['financial_scope_unbound']=bool(_UNBOUND_SCOPE.search(prefix[-20:]+match.group()+suffix) or re.search(r'(?:至|到|～|~|區間|每(?:賺進|賺取|獲得|產生|賺)?)\s*$',prefix))
            claim['foreign_currency_declared']=bool(_FOREIGN.search(prefix[-20:]+match.group()+suffix) or _CURRENCY_DECLARATION.search(suffix))
            additions.append(claim)
    unique=[]
    for claim in additions:
        key=(claim['line_number'],claim['financial_metric'],claim['reported_value'],claim['unit'].lower(),claim['financial_period_text'])
        if key not in seen:
            unique.append(claim);seen.add(key)
    result=[]
    for claim in existing:
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
    return [{**claim,'id':index+1} for index,claim in enumerate(result)]


def _financial_source(data,metric,prefix,heading='',owner_text=None):
    if metric in {'營收', '營業收入'} and _explicit_month(prefix):
        return _monthly_source(data, prefix, heading, owner_text)
    source=_source(data,metric,prefix)
    if source is not None:
        return source
    if str(data.get('financial_currency') or '').upper() not in {'TWD','NTD'} or _PARTIAL_YEAR.search(prefix):
        return None
    periods=list(_PERIOD.finditer(prefix))
    if len(periods)!=1:
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
    from source_content_selection import company_aliases
    owner = _PERIOD.sub('', owner_text if isinstance(owner_text,str) else prefix)
    # Preserve target identity before removing amount modifiers (e.g. 達 in
    # 台達電/達方). The shared scope check still rejects any remaining issuer.
    for alias in sorted(company_aliases(data), key=len, reverse=True):
        pattern = (re.escape(alias) if re.search(r'[\u3400-\u9fff]', alias)
                   else r'(?<!\w)' + re.escape(alias) + r'(?!\w)')
        owner = re.sub(pattern, '本公司', owner, flags=re.I)
    owner = re.sub(r'^\s*(?:[-*]\s*)?(?:支持證據|證據比對|具體佐證)\s*[:：]\s*', '', owner)
    owner = re.sub(r'營業收入|營收|單月|月度|高達|達到|約為|達|約|為|負|NT\$|TWD', '', owner, flags=re.I)
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


def check_financial_amount(claim: dict,snapshot: dict,tolerance_pct: float) -> dict | None:
    if not claim.get('financial_amount'):
        return None
    public={k:v for k,v in claim.items() if k not in {'context_text','financial_period_text','financial_heading','financial_owner_text','_price_history_months','_legacy_conclusion_context_missing','_technical_as_of','_technical_default_atr14'}}
    result={**public,'status':'unverifiable','verification_reason_code':'financial_period_currency_or_unit_unknown',
            'verification_scope':'snapshot_financial_amount_consistency','candidate_count':0,
            'matched_path':'','matched_value':None,'diff_pct':None,'independent_primary_source_verified':False}
    if not claim.get('financial_actual',True):
        return {**result,'verification_reason_code':'financial_projection_not_observed_fact'}
    prefix=str(claim.get('financial_period_text') or '')
    heading=str(claim.get('financial_heading') or '')
    if _explicit_month(prefix) and any(p.search(heading) for p in
            (_HEADING_PROJECTION, _HEADING_THRESHOLD, _HEADING_CONDITIONAL)):
        return {**result,'verification_reason_code':'financial_projection_not_observed_fact'}
    if claim.get('financial_scope_unbound'):
        return {**result,'verification_reason_code':'financial_amount_scope_unbound'}
    if snapshot.get('_financial_source_context')=='original_input_unavailable':
        return {**result,'verification_reason_code':'financial_original_input_unavailable'}
    data=snapshot.get('data');data=data if isinstance(data,dict) else {}
    unit=str(claim.get('unit') or '').lower()
    scale=_SCALES.get(unit.removesuffix('元'),_SCALES.get(unit))
    if scale is None or claim.get('foreign_currency_declared'):
        return result
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
    return {**result,'status':'verified' if matched else 'mismatch',
            'verification_reason_code':'matched_financial_metric_period_unit' if matched else 'financial_metric_period_unit_mismatch',
            'candidate_count':1,'matched_path':path,'matched_value':expected/scale,'diff_pct':round(diff,4),
            'financial_period':period,'financial_currency':'TWD','source_value':original,'source_unit':source_unit,
            'reported_value_raw_twd':reported,'expected_value_raw_twd':expected,
            'verification_data_source':snapshot.get('_financial_source_context','saved_snapshot'),
            'analysis_input_cutoff':snapshot.get('_financial_input_cutoff','')}


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
