"""Issuer-bound mixed insurance/merchandise totals from complete MOPS JSON.

The reported income total is neither ordinary revenue nor bank net revenue.
No taxonomy tag or standalone/group cash-flow valuation equivalence is invented.
"""
from copy import deepcopy
from datetime import date,datetime
from hashlib import sha256
import json,re,time
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError
from .mops_public_annual import (PublicMopsHttp,STATEMENTS,SOURCE_URL,api_url,
    template_url,payload,MAX_BYTES,_object,_template,_receipt)
from .official_xbrl_financial import INDEX_URL,FilingError,_filing_urls
from .official_mopsfin_financial import _amount

TICKER='2905.TW'
ISSUERS={
    TICKER:{'ticker':TICKER,'stock_id':'2905','official_name':'三商',
        'legal_name':'三商投資控股股份有限公司','official_ubn':'11052709','instrument_type':'EQUITY'},
    '2207.TW':{'ticker':'2207.TW','stock_id':'2207','official_name':'和泰車','instrument_type':'EQUITY'},
}
SCHEMA='mixed_income_consolidated_annual.v1'
PROTOCOL='mops-public-mixed-income-three-statements.v1'
PROVIDER='TWSE MOPS mixed-income annual JSON'
NOTE=('三商合併年報的收入合計包含保險及其他業務，保留 total_income 原科目，'
      '不代填一般營收、毛利、營業利益或銀行淨收益；淨利及權益採母公司歸屬，'
      '自由現金流只按同年營業現金流加明列帶符號設備與無形資產支出計算，未驗證一般業DCF適用性。')
LABELS={
    'BalanceSheet':{'assets':'資產總計','liabilities':'負債總計',
        'equity':'歸屬於母公司業主之權益合計','noncontrolling_equity':'非控制權益','total_equity':'權益總計'},
    'IncomeStatement':{'total_income':'收入合計','total_expenses':'支出合計',
        'pretax_profit':'繼續營業單位稅前淨利（淨損）','income_tax':'所得稅費用（利益）',
        'continuing_profit':'繼續營業單位本期淨利（淨損）','group_profit':'本期淨利（淨損）',
        'net_income_attributable':'母公司業主','noncontrolling_profit':'非控制股權'},
    'CashflowStatement':{'operating_cash_flow':'營業活動之淨現金流入（流出）',
        'ppe_purchase':'取得不動產、廠房及設備','intangible_purchase':'取得無形資產'},
}
FIELDS=tuple(k for labels in LABELS.values()for k in labels)+('free_cash_flow',)


def supports_annual(ticker):return isinstance(ticker,str) and ticker in ISSUERS


def origin_note(ticker):
    if ticker==TICKER:return NOTE
    if ticker=='2207.TW':
        return ('和泰車合併年報的收入合計包含汽車銷售、利息、保費及其他業務，保留 total_income 原科目，'
            '不代填一般營收、毛利、營業利益或銀行淨收益；淨利及權益採母公司歸屬，'
            '自由現金流只按同年營業現金流加明列帶符號設備與無形資產支出計算，未驗證一般業DCF適用性。')
    raise FilingError('mixed income issuer not admitted')


def validate_context(data,ticker):
    if not supports_annual(ticker):return
    identity=data.get('company_identity')or{}
    expected=ISSUERS[ticker]
    if not isinstance(identity,dict)or any(identity.get(k)not in(None,'',v)for k,v in expected.items()):
        raise ValueError('mixed_income_annual_issuer_conflict')
    forbidden=identity.get('forbidden_aliases',[])
    if (not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)
            or {expected[k] for k in ('official_name','legal_name') if k in expected}&{v.strip()for v in forbidden}):
        raise ValueError('mixed_income_annual_forbidden_issuer')


def parse_statement(raw,ticker,year,statement,template):
    if (not supports_annual(ticker) or statement not in STATEMENTS or type(year)is not int
            or not 2013<=year<date.today().year or not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES):
        raise FilingError('mixed income statement identity or body invalid')
    _template(template,statement)
    try:
        v=json.loads(raw.decode('utf8',errors='strict'),object_pairs_hook=_object);r=v['result']
        if (type(v['code'])is not int or v['code']!=200 or not isinstance(r,dict)
                or r['reportType']!='合併'or r['year']!=str(year-1911)or r['season']!='4'
                or type(r['fiscalYear'])is not str or r['fiscalYear'].strip()
                or r['companyAbbreviation']!=ISSUERS[ticker]['official_name']or not isinstance(r.get('subsidiary'),list)
                or r.get('subsidiaryCompanyId','')not in(None,'')
                or any(k in r for k in ('currency','unit','scale'))):
            raise FilingError('mixed income scope, period or unit metadata invalid')
        refs=[x['url']for x in r['urlList']if isinstance(x,dict)and x.get('name')=='XBRL資訊平台']
        if len(refs)!=1:raise FilingError('mixed income issuer reference ambiguous')
        p=urlsplit(refs[0])
        if (p.scheme!='https'or p.netloc!='mopsov.twse.com.tw'or p.path!='/server-java/t164sb01'or p.fragment
                or parse_qs(p.query,keep_blank_values=True)!={'step':['1'],'CO_ID':[ISSUERS[ticker]['stock_id']],
                    'SYEAR':[str(year)],'SSEASON':['4'],'REPORT_ID':['C']}):
            raise FilingError('mixed income issuer reference mismatch')
        suffix='年12月31日'if statement=='BalanceSheet'else'年度'
        sub=[{'main':'金額','sub':[]}]+([]if statement=='CashflowStatement'else[{'main':'%','sub':[]}])
        titles=[{'main':'會計項目','sub':[]},{'main':str(year-1911)+suffix,'sub':sub},{'main':str(year-1912)+suffix,'sub':sub}]
        if r['titles']!=titles:raise FilingError('mixed income monetary period columns invalid')
        rows=r['reportList'];width=3 if statement=='CashflowStatement'else 5
        if (not isinstance(rows,list)or not 1<=len(rows)<=400
                or any(not isinstance(x,list)or len(x)!=width or not isinstance(x[0],str)for x in rows)):
            raise FilingError('mixed income rows invalid')
        attribution=[]
        if statement=='IncomeStatement':
            def heading(label):
                ix=[i for i,x in enumerate(rows)if x[0].strip()==label]
                if len(ix)!=1 or any(x!=''for x in rows[ix[0]][1:]):
                    raise FilingError('mixed income attribution heading invalid')
                return ix[0]
            start=heading('淨利（淨損）歸屬於：');end=heading('綜合損益總額歸屬於：')
            if end!=start+3:raise FilingError('mixed income attribution section ambiguous')
            attribution=rows[start+1:end]
        facts={year:{},year-1:{}}
        for field,label in LABELS[statement].items():
            source=attribution if field in ('net_income_attributable','noncontrolling_profit')else rows
            matches=[x for x in source if x[0].strip()==label]
            if len(matches)!=1:raise FilingError('mixed income missing or duplicate fact: '+label)
            for period,col in ((year,1),(year-1,2 if statement=='CashflowStatement'else 3)):
                text=matches[0][col]
                if type(text)is not str or len(text)>40:raise FilingError('mixed income monetary fact invalid')
                n=_amount(text,label=label)
                if field in ('ppe_purchase','intangible_purchase')and n>0:
                    raise FilingError('mixed income purchase sign invalid')
                facts[period][field]=n
        for row in facts.values():
            if statement=='BalanceSheet'and (row['assets']!=row['liabilities']+row['total_equity']
                    or row['total_equity']!=row['equity']+row['noncontrolling_equity']):
                raise FilingError('mixed income balance equations do not reconcile')
            if statement=='IncomeStatement'and (row['total_income']-row['total_expenses']!=row['pretax_profit']
                    or row['pretax_profit']-row['income_tax']!=row['continuing_profit']
                    or row['net_income_attributable']+row['noncontrolling_profit']!=row['group_profit']):
                raise FilingError('mixed income profit equations do not reconcile')
        return facts
    except (KeyError,TypeError,ValueError,UnicodeError,IndexError)as exc:
        if isinstance(exc,FilingError):raise
        raise FilingError('mixed income JSON metadata or facts invalid')from exc


def _close(year):return datetime(year+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()


def _select(index,ticker=TICKER):
    if not supports_annual(ticker):raise FilingError('mixed income issuer not admitted')
    text=index.decode('utf8','strict')
    starts=list(re.finditer(r'<html\b[^>]*>',text,re.I));ends=list(re.finditer(r'</html\s*>',text,re.I))
    if (len(starts)!=1 or len(ends)!=1 or starts[0].start()>=ends[0].start()
            or text[ends[0].end():].strip()):raise FilingError('mixed income published index incomplete')
    issuer=ISSUERS[ticker]['stock_id']
    urls=_filing_urls(index,issuer);years=sorted(urls)[-5:];individual=_filing_urls(index,issuer,report_id='A')
    if (len(years)!=5 or years!=list(range(years[0],years[0]+5))or years[-1]>=date.today().year
            or individual and max(individual)>years[-1]):raise FilingError('mixed income five latest published C filings invalid')
    return years,urls


def _assemble(documents,years,ticker=TICKER):
    if not supports_annual(ticker):raise FilingError('mixed income issuer not admitted')
    issuer=ISSUERS[ticker]['stock_id']
    primary={};comparative={};templates={}
    for year,doc in zip(years,documents):
        if (not isinstance(doc,dict)or type(doc.get('year'))is not int or doc['year']!=year
                or doc.get('period_end')!=f'{year}-12-31'or doc.get('provider')!=PROVIDER
                or doc.get('report_scope')!='consolidated'or doc.get('url')!=api_url('BalanceSheet')
                or doc.get('format')!=PROTOCOL or not isinstance(doc.get('components'),list)or len(doc['components'])!=3):
            raise FilingError('mixed income annual document invalid')
        facts={};prior={}
        for s,part in zip(STATEMENTS,doc['components']):
            if (not isinstance(part,dict)or type(part.get('year'))is not int or part['year']!=year
                    or part.get('statement')!=s or part.get('url')!=api_url(s)or part.get('request')!=payload(issuer,year)):
                raise FilingError('mixed income source request invalid')
            raw=_receipt(part['raw_receipt'],api_url(s),not_before=_close(year))
            if sha256(raw).hexdigest()!=part.get('sha256'):raise FilingError('mixed income original digest differs')
            tr=part['unit_template_receipt'];key=json.dumps(tr,sort_keys=True)
            if key not in templates:templates[key]=_receipt(tr,template_url(s),not_before=_close(years[-1]))
            parsed=parse_statement(raw,ticker,year,s,templates[key]);facts.update(parsed[year]);prior.update(parsed[year-1])
        if doc.get('sha256')!=sha256(';'.join(p['sha256']for p in doc['components']).encode()).hexdigest():
            raise FilingError('mixed income annual manifest digest differs')
        primary[year]=facts
        if year>years[0]:comparative[year-1]=prior
    revisions=[]
    for year,prior in comparative.items():
        if set(prior)!=set(primary[year]):raise FilingError('mixed income comparative contract differs')
        for fact,n in prior.items():
            original=primary[year][fact]
            if n!=original:
                revisions.append({'year':year,'fact':fact,'original_twd':original,'revised_twd':n,
                    'original_filing_year':year,'comparative_filing_year':year+1,'kind':'restatement'})
                primary[year][fact]=n
    rows={str(y):{**r,'free_cash_flow':r['operating_cash_flow']+r['ppe_purchase']+r['intangible_purchase']}for y,r in primary.items()}
    return rows,sorted(revisions,key=lambda x:(x['year'],x['fact']))


def project_history(value,ticker):
    try:
        if (not supports_annual(ticker) or not isinstance(value,dict)or value.get('ticker')!=ticker
                or value.get('schema')!=SCHEMA or value.get('protocol')!=PROTOCOL
                or value.get('currency')!='TWD'or value.get('report_scope')!='consolidated'
                or value.get('source_url')!=SOURCE_URL):return None
        years=value['years'];docs=value['documents']
        if (not isinstance(years,list)or len(years)!=5 or any(type(y)is not str or len(y)!=4 or not y.isdigit()for y in years)
                or not isinstance(docs,list)or len(docs)!=5):return None
        index=_receipt(value['published_index_receipt'],INDEX_URL,2500000,not_before=_close(int(years[-1])))
        selected,urls=_select(index,ticker)
        if years!=list(map(str,selected))or any(not isinstance(d,dict)or d.get('indexed_xbrl_url')!=urls[y]for d,y in zip(docs,selected)):return None
        saved=value['raw_twd_by_year']
        if (not isinstance(saved,dict)or set(saved)!=set(years)or any(not isinstance(r,dict)
                or set(r)!=set(FIELDS)or any(type(n)is not int for n in r.values())for r in saved.values())):return None
        rows,revisions=_assemble(docs,selected,ticker)
        if rows!=saved or json.dumps(revisions,sort_keys=True)!=json.dumps(value['comparative_revisions'],sort_keys=True):return None
        from ..financial_history_basis import _history_projection
        labels={'net_income_history':('net_income_attributable','淨利（淨損）歸屬於：母公司業主'),
            'total_assets_history':('assets','資產總計'),'total_equity_history':('equity','歸屬於母公司業主之權益合計'),
            'fcf_history':('free_cash_flow','營業現金流加明列設備與無形資產支出')}
        fields={key:(field,'mops-public-mixed-income-row:'+label,label)for key,(field,label)in labels.items()}
        return {**_history_projection(rows,years,ticker,schema=SCHEMA,common_fields=fields,
            unsupplied_fields=('revenue_history','gross_profit_history','operating_income_history'),scope='consolidated',note=origin_note(ticker)),
            'sector_specific_financials':deepcopy(value)}
    except (KeyError,ValueError,TypeError,OverflowError,OSError,EOFError,AttributeError):return None


def fetch_histories(ticker,*,transport=None):
    if not supports_annual(ticker):raise FilingError('mixed income issuer not admitted')
    issuer=ISSUERS[ticker]['stock_id']
    http=transport or PublicMopsHttp()
    with http.batch():
        index,index_receipt=http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':issuer})
        years,urls=_select(index,ticker);templates={s:http.request(template_url(s))for s in STATEMENTS};docs=[]
        for s,(raw,_)in templates.items():_template(raw,s)
        for year in years:
            parts=[]
            for s in STATEMENTS:
                raw,receipt=http.request(api_url(s),json_body=payload(issuer,year))
                parse_statement(raw,ticker,year,s,templates[s][0])
                parts.append({'year':year,'statement':s,'url':api_url(s),'request':payload(issuer,year),
                    'sha256':sha256(raw).hexdigest(),'raw_receipt':receipt,'unit_template_receipt':templates[s][1]})
            docs.append({'year':year,'period_end':f'{year}-12-31','provider':PROVIDER,'report_scope':'consolidated',
                'url':api_url('BalanceSheet'),'indexed_xbrl_url':urls[year],'format':PROTOCOL,'components':parts,
                'sha256':sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest()})
        rows,revisions=_assemble(docs,years,ticker)
        value={'ticker':ticker,'schema':SCHEMA,'protocol':PROTOCOL,'currency':'TWD','report_scope':'consolidated',
            'source_url':SOURCE_URL,'published_index_receipt':index_receipt,'years':list(map(str,years)),
            'documents':docs,'raw_twd_by_year':rows,'comparative_revisions':revisions}
        if project_history(value,ticker)is None:raise FilingError('mixed income full original projection rejected')
    if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
    return value


def fetch_result(ticker,*,transport=None):
    from source_audit import audited_fetch
    http=transport or PublicMopsHttp()
    def acquire():
        try:return fetch_histories(ticker,transport=http)
        except (FilingError,SourceResponseError):raise
        except Exception as exc:raise FilingError('mixed income acquisition failed closed: '+type(exc).__name__)from exc
    result=audited_fetch('financial_statements',PROVIDER,acquire,default=None,record_counter=lambda v:len(v['years']))
    sent=sum(c.get('http_request_sent')is True for c in http.components)
    result['audit'].update(http_request_sent=bool(sent),http_request_count=sent,
        event_kind='aggregate'if sent else'local_block',component_statuses={str(i):deepcopy(c)for i,c in enumerate(http.components)})
    if http.components:result['audit']['http_status']=http.components[-1].get('http_status')
    return result
