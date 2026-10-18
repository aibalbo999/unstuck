"""Issuer-bound ordinary individual histories; never relabel A as consolidated.

Admission starts with the qualified issuer. Every future query discovers periods
again, prefers a complete C basis, and otherwise requires five unmixed A filings.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
import time
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from .official_xbrl_financial import (FilingError, INDEX_URL, MAX_BYTES, NUMBER_RE,
    IX, XBRLI, _context_period, _filing_urls)
from .mops_public_annual import PublicMopsHttp, _receipt, _fetch_public_annual_histories

SCHEMA='ordinary_individual.v1'
PROVIDER='TWSE MOPS issuer annual statements'
ISSUERS={'2646.TW':'星宇航空股份有限公司','2033.TW':'佳大世界股份有限公司'}
# Short published series are admitted only to separate annual references, not
# the canonical five-year source or its issuer routing.
REFERENCE_ISSUERS={'1623.TW':'大東電業廠股份有限公司','7799.TW':'禾榮科技股份有限公司'}
ISSUER_NAME_ALIASES={
    '2646.TW':frozenset({'星宇航空','星宇航空股份有限公司'}),
    '2033.TW':frozenset({'佳大','佳大世界','佳大世界股份有限公司'}),
}
FIELDS={'Revenue':'reported_revenue','ProfitLoss':'profit_loss','GrossProfit':'gross_profit',
        'ProfitLossFromOperatingActivities':'operating_income','Assets':'assets','Equity':'equity',
        'CashFlowsFromUsedInOperatingActivities':'operating_cash_flow',
        'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities':'ppe_purchase',
        'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities':'intangible_purchase'}
COMMON_FIELDS={key:(field,'ifrs-full:'+tag,label)for key,tag,field,label in (
    ('revenue_history','Revenue','reported_revenue','個別營業收入'),
    ('net_income_history','ProfitLoss','profit_loss','個別本期損益'),
    ('gross_profit_history','GrossProfit','gross_profit','個別營業毛利'),
    ('operating_income_history','ProfitLossFromOperatingActivities','operating_income','個別營業利益'),
    ('total_assets_history','Assets','assets','個別資產總額'),
    ('total_equity_history','Equity','equity','個別權益總額'))}
COMMON_FIELDS['fcf_history']=('free_cash_flow','operating_cash_flow+ppe_purchase+intangible_purchase','個別營業現金流加明列設備及無形資產現金支出')
NOTE='五年一般業個別報表；本期損益及權益不改稱母公司歸屬或合併集團，未證明無子公司。年度序列與保留股價/TTM純量口徑不可混用估值。無形資產購置未列示時，僅在官方投資活動明細與淨額精確勾稽後才以零補入，並保留推算憑據。'

def supports_annual(ticker):return isinstance(ticker,str) and ticker in ISSUERS

def validate_context(data,ticker):
    if not supports_annual(ticker) or not isinstance(data,dict) or data.get('ticker')!=ticker:
        raise ValueError('ordinary_individual_identity_not_verified')
    identity=data.get('company_identity')
    if identity is not None and not isinstance(identity,dict):raise ValueError('ordinary_individual_identity_not_verified')
    for item in (data,identity or {}):
        for key,expected in (('ticker',ticker),('stock_id',ticker.split('.')[0])):
            if key in item and item[key] not in (None,expected):raise ValueError('ordinary_individual_identity_conflict')
        for key in ('quote_type','quoteType','instrument_type'):
            if key in item and item[key] not in (None,'EQUITY'):raise ValueError('ordinary_individual_instrument_conflict')
    for key in ('official_name','legal_name'):
        name=(identity or {}).get(key)
        if name is not None and name not in ISSUER_NAME_ALIASES.get(ticker,{ISSUERS[ticker]}):raise ValueError('ordinary_individual_name_conflict')

def individual_url(url):
    try:
        p=urlsplit(url);q=parse_qs(p.query,keep_blank_values=True)
        return (p.scheme=='https'and p.netloc=='mopsov.twse.com.tw'and p.path=='/server-java/FileDownLoad'
                and not p.fragment and set(q)=={'functionName','step','co_id','year','season','report_id'}
                and q['functionName']==['t164sb01']and q['step']==['9']and q['season']==['4']and q['report_id']==['A']
                and len(q['co_id'])==len(q['year'])==1 and q['co_id'][0]+'.TW'in ISSUERS
                and re.fullmatch(r'20\d{2}',q['year'][0])is not None and 2013<=int(q['year'][0])<date.today().year)
    except (TypeError,ValueError,KeyError):return False

class IndividualMopsHttp(PublicMopsHttp):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.individual_downloads=True

def select_basis(index,issuer):
    c=_filing_urls(index,issuer);a=_filing_urls(index,issuer,report_id='A')
    latest=max([*c,*a],default=0)
    years=sorted(c)[-5:]
    if (len(years)in(4,5)and years==list(range(years[0],years[-1]+1))
            and years[-1]==latest and years[-1]<date.today().year and (len(years)==5 or years[0]>2013)):
        return 'consolidated',years
    years=sorted(a)[-5:]
    if (len(years)!=5 or years!=list(range(years[0],years[-1]+1))or years[-1]>=date.today().year
            or any(y in c for y in years)or any(y>years[-1]for y in c)):
        raise FilingError('no complete unmixed latest five-year ordinary individual basis')
    return 'individual',years

def _cashflow_fact_twd(fact,units):
    text=''.join(fact.itertext()).strip()
    if (units.get(fact.get('unitRef'))!='iso4217:TWD'or fact.get('format')!='ixt:numdotdecimal'
            or fact.get('scale')!='3'or fact.get('decimals')not in('-3','INF')
            or fact.get('sign')not in(None,'-')or len(text)>40 or not NUMBER_RE.fullmatch(text)):
        raise FilingError('individual investing cash-flow fact invalid')
    value=Decimal(text.replace(',',''))*1000
    if value!=value.to_integral_value():raise FilingError('individual investing cash-flow fact is fractional TWD')
    return int(value)*(-1 if fact.get('sign')=='-'else 1)

def _investing_cashflow_reconciliation(root,contexts,units,year):
    period=('duration',f'{year}-01-01',f'{year}-12-31');matches=[]
    for table in root.iter():
        if table.tag.rsplit('}',1)[-1].lower()!='table':continue
        rows=[node for node in table.iter()if node.tag.rsplit('}',1)[-1].lower()=='tr']
        for start,row in enumerate(rows):
            header=' '.join(''.join(row.itertext()).split())
            if '投資活動之現金流量'not in header and 'Cash flows from (used in) investing activities'not in header:continue
            detail=[];total=None;valid=True
            for current in rows[start+1:]:
                text=' '.join(''.join(current.itertext()).split())
                cells=[cell for cell in current if cell.tag.rsplit('}',1)[-1].lower()in{'td','th'}]
                code_text=' '.join(''.join(cells[0].itertext()).split())if cells else text
                code_match=re.match(r'^(BBBB|B\d{4,})\b',code_text);code=code_match.group(1)if code_match else''
                facts=[fact for fact in current.iter(IX+'nonFraction')if contexts.get(fact.get('contextRef'))==period]
                if code=='BBBB':
                    if (len(facts)!=1 or facts[0].get('name')not in {
                            'ifrs-full:CashFlowsFromUsedInInvestingActivities',
                            'tifrs-SCF:CashFlowsFromUsedInInvestingActivities',
                            'tifrs-SCF:NetCashFlowsFromUsedInInvestingActivities'}):valid=False
                    else:total=_cashflow_fact_twd(facts[0],units)
                    break
                if re.fullmatch(r'B\d{4,}',code):
                    if (re.search(r'無形資產|intangible',text,re.IGNORECASE)
                            or any('intang' in str(fact.get('name')or'').lower()for fact in facts)
                            or len(facts)!=1):valid=False;break
                    detail.append(_cashflow_fact_twd(facts[0],units))
                elif text:
                    valid=False;break
            if valid and total is not None and detail:matches.append((sum(detail),total,len(detail)))
    if len(matches)!=1:return None
    detail_total,statement_total,row_count=matches[0]
    if detail_total!=statement_total:return None
    return {'detail_sum_twd':detail_total,'statement_total_twd':statement_total,'detail_row_count':row_count}

def parse_individual_filing(raw,issuer,filing_year,*,reference_only=False):
    admitted={**ISSUERS,**REFERENCE_ISSUERS}if reference_only else ISSUERS
    if (not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES or b'<!DOCTYPE'in raw.upper()or b'<!ENTITY'in raw.upper()
            or issuer+'.TW'not in admitted or type(filing_year)is not int or not 2013<=filing_year<date.today().year):
        raise FilingError('individual filing identity or body invalid')
    try:root=ET.fromstring(raw)
    except ET.ParseError as exc:raise FilingError('individual filing is not complete XML')from exc
    if root.tag!='{http://www.w3.org/1999/xhtml}html':raise FilingError('individual filing is not inline XHTML')
    contexts={};units={}
    for n in root.iter(XBRLI+'context'):
        key=n.get('id')
        if not key or key in contexts:raise FilingError('duplicate individual context')
        contexts[key]=_context_period(n,issuer)
    if {n.text for n in root.iter(XBRLI+'identifier')}!={issuer}:raise FilingError('individual filing contains another issuer')
    for n in root.iter(XBRLI+'unit'):
        key=n.get('id')
        if not key or key in units:raise FilingError('duplicate individual unit')
        units[key]=n.findtext(XBRLI+'measure')
    duration=('duration',f'{filing_year}-01-01',f'{filing_year}-12-31')
    report_type=('Financial report (first time adoption)'if reference_only and issuer=='7799'and filing_year==2023
                 else'Financial report (general)')
    for tag,expected in {'CompanyID':issuer,'CompanyChineseName':admitted[issuer+'.TW'],'Year':str(filing_year),'Quarter':'4',
                         'ReportCategory':'Individual report','ReportType':report_type,
                         'IndustrySector':'Commercial and industrial'}.items():
        matches=[n for n in root.iter(IX+'nonNumeric')if n.get('name')=='tifrs-notes:'+tag]
        if len(matches)!=1 or contexts.get(matches[0].get('contextRef'))!=duration or ''.join(matches[0].itertext()).strip()!=expected:
            raise FilingError('individual scope metadata mismatch: '+tag)
    rows={};inferred_zero_facts=[]
    for year in (filing_year,filing_year-1):
        row={}
        for n in root.iter(IX+'nonFraction'):
            name=n.get('name','');tag=name.removeprefix('ifrs-full:')
            if not name.startswith('ifrs-full:')or tag not in FIELDS:continue
            period=('instant',f'{year}-12-31')if tag in('Assets','Equity')else('duration',f'{year}-01-01',f'{year}-12-31')
            if contexts.get(n.get('contextRef'))!=period:continue
            field=FIELDS[tag];text=''.join(n.itertext()).strip()
            if (field in row or units.get(n.get('unitRef'))!='iso4217:TWD'or n.get('format')!='ixt:numdotdecimal'
                    or n.get('scale')!='3'or n.get('decimals')not in('-3','INF')or n.get('sign')not in(None,'-')
                    or len(text)>40 or not NUMBER_RE.fullmatch(text)):
                raise FilingError('individual numeric fact invalid: '+tag)
            value=Decimal(text.replace(',',''))*1000
            if value!=value.to_integral_value():raise FilingError('individual fractional TWD unsupported')
            row[field]=int(value)*(-1 if n.get('sign')=='-'else 1)
            if tag.startswith('PurchaseOf')and row[field]>0:raise FilingError('individual cash purchase sign invalid')
        if set(FIELDS.values())-set(row)-{'intangible_purchase'}:raise FilingError('individual necessary annual facts missing')
        if 'intangible_purchase'not in row:
            proof=_investing_cashflow_reconciliation(root,contexts,units,year)
            if proof is not None:
                row['intangible_purchase']=0
                inferred_zero_facts.append({'period_year':year,'fact':'PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities',
                    'value_twd':0,'filing_year':filing_year,'proof':'mops_individual_investing_detail_reconciles',**proof})
        rows[year]=row
    return {**rows,'inferred_zero_facts':inferred_zero_facts}

def _assemble(primary,comparatives):
    rows=deepcopy(primary);revisions=[];required=set(FIELDS.values())
    for year,prior in comparatives.items():
        original=rows[year];conflicts={k:(original[k],v)for k,v in prior.items()if k in original and original[k]!=v}
        if conflicts and set(prior)!=required:raise FilingError('conflicting incomplete individual comparative')
        for key,value in prior.items():
            if key not in original or original[key]!=value:
                revisions.append({'year':year,'fact':key,'original_twd':original.get(key),'revised_twd':value,
                                  'original_filing_year':year,'comparative_filing_year':year+1,
                                  'kind':'missing_fact_fill'if key not in original else'restatement'})
        rows[year]=deepcopy(prior)if set(prior)==required else {**prior,**original}
    result={}
    for year,row in sorted(rows.items()):
        if set(row)!=required or any(type(v)is not int for v in row.values()):raise FilingError('individual annual facts incomplete')
        result[str(year)]={**row,'free_cash_flow':row['operating_cash_flow']+row['ppe_purchase']+row['intangible_purchase']}
    return result,revisions

def _project(rows,years,ticker):
    from ..financial_history_basis import _history_projection
    return _history_projection(rows,years,ticker,schema=SCHEMA,common_fields=COMMON_FIELDS,unsupplied_fields=(),scope='individual',note=NOTE)

def project_individual_history(value,ticker):
    try:
        if (not supports_annual(ticker)or not isinstance(value,dict)or value.get('schema')!=SCHEMA or value.get('ticker')!=ticker
                or value.get('currency')!='TWD'or value.get('report_scope')!='individual'or value.get('source_url')!=INDEX_URL):return None
        issuer=ticker.split('.')[0];years=value['years'];documents=value['documents']
        if not isinstance(years,list)or len(years)!=5 or any(type(y)is not str or not re.fullmatch(r'20\d{2}',y)for y in years):return None
        close=datetime(int(years[-1])+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        index=_receipt(value['published_index_receipt'],INDEX_URL,2500000,not_before=close)
        scope,selected=select_basis(index,issuer)
        if scope!='individual'or years!=[str(y)for y in selected]or not isinstance(documents,list)or len(documents)!=5:return None
        urls=_filing_urls(index,issuer,report_id='A');primary={};prior={};inferred_zero_facts=[]
        for y,doc in zip(selected,documents):
            if (not isinstance(doc,dict)or type(doc.get('year'))is not int or doc['year']!=y or doc.get('period_end')!=f'{y}-12-31'
                    or doc.get('url')!=urls[y]or doc.get('provider')!=PROVIDER or doc.get('report_scope')!='individual'):return None
            raw=_receipt(doc['raw_receipt'],urls[y],MAX_BYTES,not_before=datetime(y+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp())
            if sha256(raw).hexdigest()!=doc.get('sha256'):return None
            parsed=parse_individual_filing(raw,issuer,y);primary[y]=parsed[y]
            inferred_zero_facts.extend(item for item in parsed['inferred_zero_facts']if item['period_year']==y)
            if y>selected[0]:prior[y-1]=parsed[y-1]
        rows,revisions=_assemble(primary,prior)
        saved=value['raw_twd_by_year']
        if (not isinstance(saved,dict)or set(saved)!=set(years)
                or any(not isinstance(row,dict)or set(row)!=set(FIELDS.values())|{'free_cash_flow'}
                       or any(type(n)is not int for n in row.values())for row in saved.values())):return None
        if rows!=saved or json.dumps(revisions,sort_keys=True)!=json.dumps(value['comparative_revisions'],sort_keys=True):return None
        inferred_zero_facts=sorted(inferred_zero_facts,key=lambda item:(item['period_year'],item['fact']))
        if ('inferred_zero_facts'in value and json.dumps(value['inferred_zero_facts'],sort_keys=True)!=json.dumps(inferred_zero_facts,sort_keys=True)):
            return None
        if inferred_zero_facts and 'inferred_zero_facts'not in value:return None
        projected=_project(rows,years,ticker)
        if projected is None:return None
        return {**projected,'sector_specific_financials':deepcopy(value)}
    except (KeyError,TypeError,ValueError,OverflowError,OSError,EOFError):return None

def _fetch_consolidated(ticker,http,index_original):
    return _fetch_public_annual_histories(ticker,http,index_original=index_original)

def fetch_annual_histories(ticker,http):
    if not supports_annual(ticker):raise FilingError('ordinary individual issuer not admitted')
    issuer=ticker.split('.')[0]
    with http.batch():
        index,receipt=http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':issuer})
        scope,years=select_basis(index,issuer)
        if scope=='consolidated':return _fetch_consolidated(ticker,http,(index,receipt))
        urls=_filing_urls(index,issuer,report_id='A');primary={};prior={};docs=[];inferred_zero_facts=[]
        for year in years:
            raw,proof=http.request(urls[year]);parsed=parse_individual_filing(raw,issuer,year);primary[year]=parsed[year]
            inferred_zero_facts.extend(item for item in parsed['inferred_zero_facts']if item['period_year']==year)
            if year>years[0]:prior[year-1]=parsed[year-1]
            docs.append({'year':year,'period_end':f'{year}-12-31','url':urls[year],'provider':PROVIDER,'report_scope':'individual',
                         'sha256':sha256(raw).hexdigest(),'raw_receipt':proof})
        rows,revisions=_assemble(primary,prior)
        inferred_zero_facts=sorted(inferred_zero_facts,key=lambda item:(item['period_year'],item['fact']))
        value={'schema':SCHEMA,'ticker':ticker,'currency':'TWD','report_scope':'individual','source_url':INDEX_URL,
               'years':[str(y)for y in years],'raw_twd_by_year':rows,'documents':docs,'published_index_receipt':receipt,
               'comparative_revisions':revisions,'inferred_zero_facts':inferred_zero_facts}
        if project_individual_history(value,ticker)is None:raise FilingError('individual full original replay failed')
        if time.monotonic()>=http.deadline:raise FilingError('individual query deadline exceeded')
        return value

def fetch_annual_result(ticker,*,transport=None):
    from source_audit import audited_fetch
    from search_provider_runtime import SourceResponseError
    from provider_resilience import _check_provider_state,ProviderCircuitOpenError,ProviderRateLimitOpenError
    from provider_throttle import enforce_provider_throttle
    from .mops_public_annual import PROVIDER as PUBLIC_PROVIDER
    http=transport or IndividualMopsHttp();errors=[]
    def acquire():
        try:
            # A new truthful protocol label never bypasses the existing host's
            # aggregate circuit, rate cooldown or pacing. Endpoint guards remain
            # in PublicMopsHttp for every request.
            _check_provider_state(PUBLIC_PROVIDER)
            enforce_provider_throttle(PUBLIC_PROVIDER)
            return fetch_annual_histories(ticker,http)
        except (FilingError,SourceResponseError,ProviderCircuitOpenError,ProviderRateLimitOpenError)as exc:
            errors.append(exc);raise
        except Exception as exc:raise FilingError('individual acquisition failed closed: '+type(exc).__name__)from exc
    result=audited_fetch('financial_statements',PROVIDER,acquire,default=None,
                        record_counter=lambda v:len(v['years']),success_message='五年同口徑官方年度原件已核對，科目保留原申報範圍。')
    audit=result['audit'];sent=sum(c.get('http_request_sent')is True for c in http.components)
    audit.update(http_request_sent=bool(sent),http_request_count=sent,event_kind='aggregate'if sent else'local_block',
                 component_statuses={str(i):deepcopy(c)for i,c in enumerate(http.components)})
    if http.components:audit['http_status']=http.components[-1].get('http_status')
    if errors:audit['error_kind']=getattr(errors[-1],'error_kind',type(errors[-1]).__name__)
    return result
