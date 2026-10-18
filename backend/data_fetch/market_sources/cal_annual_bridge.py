"""Five MOPS years plus issuer-published audited cash flow originals.

Only the exact missing intangible purchase fact is supplemented. Both other
cash facts must match the same issuer/year MOPS facts, including comparisons.
"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime,date
from hashlib import sha256
import json,time,zlib
from zoneinfo import ZoneInfo
from .cal_annual_transport import BridgeHttp,PROVIDER,MASTER_URL,MASTER_JSON_URL,IR_URL,PDF_YEARS,parse_master,parse_index,fetch_master
from .cal_audited_cash import parse_book,LABELS
from .mops_public_annual import STATEMENTS,INDEX_URL,api_url,template_url,payload,parse_statement,_template,_receipt
from .official_xbrl_financial import FIELDS,FilingError,_filing_urls,assemble_annual_histories,reconcile_comparative_rows
from source_pdf_reader import SourcePdfError
from search_provider_runtime import SourceResponseError
from .annual_issuer_master import read_master, is_shared, current_at, body_audit

TICKER='2610.TW';SOURCE_URL=IR_URL
POLICY='cal-mops-five-years-and-published-audited-cash.v1'
YEARS=[2021,2022,2023,2024,2025]
PUBLIC_PROVIDER='TWSE MOPS public annual JSON'
INTANGIBLE='PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'
NOTE=('五年年度財報採MOPS公開合併三表；無形資產支出由華航官網2022、2024、2025年度查核合併財報英文譯本補齊，'
      '各期營業現金流及設備支出均與MOPS核對。2021、2023的補充數字來自次年明示比較欄，未宣稱為當時原始申報；'
      '英文與中文有衝突時以中文原件為準。自由現金流按同年營業現金流加帶符號設備及無形資產支出計算。')
def supports_bridge(ticker):return ticker==TICKER and date.today().year==2026
def _same(a,b):return json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False)==json.dumps(b,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _bad(reason):raise FilingError('China Airlines annual bridge '+reason)
def bridge_origin_note(value):
    return NOTE if isinstance(value,dict)and value.get('ticker')==TICKER and value.get('source_basis')==POLICY and value.get('source_url')==SOURCE_URL else None
def validate_bridge_context(data,ticker):
    if ticker!=TICKER:return
    identity=data.get('company_identity')or{}
    if not isinstance(identity,dict):raise ValueError('annual_bridge_identity_invalid')
    for key,expected in [('ticker',TICKER),('stock_id','2610'),('official_name','華航'),('legal_name','中華航空股份有限公司'),('official_ubn','11145904'),('instrument_type','EQUITY')]:
        if identity.get(key)not in(None,'',expected):raise ValueError('annual_bridge_identity_conflict')
    if any(data.get(k)not in(None,'','EQUITY')for k in('instrument_type','quote_type','quoteType')):raise ValueError('annual_bridge_instrument_conflict')
    forbidden=identity.get('forbidden_aliases',[])
    if not isinstance(forbidden,(list,tuple))or any(not isinstance(s,str)for s in forbidden)or {'華航','中華航空股份有限公司','china airlines'}&{s.strip().casefold()for s in forbidden}:raise ValueError('annual_bridge_forbidden_issuer')

def _native(receipt,url,limit=250000):
    if url==IR_URL:
        from .cal_ir_gzip import is_marked,read_original
        if is_marked(receipt):return read_original(receipt)
    if (not isinstance(receipt,dict)or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified')is not False or receipt.get('finality_guaranteed')is not False
            or any(k in receipt and receipt[k]is not True for k in('http_status_observed','http_request_sent'))
            or any(k in receipt and receipt[k]is not False for k in('cache_hit','stale'))
            or any(k in receipt for k in('cache_source','source_payload_sha256','source_payload_bytes','cache_verified_at_epoch','cache_fresh_until_epoch'))):_bad('native receipt contradicts actual original')
    return _receipt(receipt,url,limit,not_before=datetime(2026,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp())

def _book(raw,year,deadline):
    remaining=10 if deadline is None else min(10,deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    p=parse_book(raw,year,timeout_seconds=remaining)
    return {**p,'facts':{str(y):r for y,r in p['facts'].items()}}

def _project(original,*,deadline=None,acquiring=False):
    master_url=original['issuer_master_receipt'].get('source_url')
    if master_url not in {MASTER_URL,MASTER_JSON_URL}:_bad('issuer master source invalid')
    mr=original['issuer_master_receipt']
    master=read_master(mr,lambda r,u:_native(r,u,2_500_000),max_age=1800 if acquiring else 100*366*86400)
    original_date=datetime.fromtimestamp(mr['retrieved_at'],ZoneInfo('Asia/Taipei')).date()
    identity=parse_master(master,source_url=master_url,today=original_date if is_shared(mr)and not acquiring else None)
    if date.fromisoformat(identity['master_as_of'])>datetime.fromtimestamp(original['issuer_master_receipt']['retrieved_at'],ZoneInfo('Asia/Taipei')).date():_bad('master future publication')
    index=_native(original['published_annual_index_receipt'],INDEX_URL,2_500_000)
    if sorted(_filing_urls(index,'2610'))[-5:]!=YEARS:_bad('published five annual periods changed')
    links=parse_index(_native(original['issuer_ir_index_receipt'],IR_URL,1_500_000))
    supplements=original['supplement_documents'];docs=original['documents']
    if not isinstance(supplements,list)or len(supplements)!=3 or not isinstance(docs,list)or len(docs)!=5:_bad('original document coverage incomplete')
    pdf_facts={};pdf_origins={};books=[]
    for year,doc in zip(PDF_YEARS,supplements):
        if type(doc.get('year'))is not int or doc['year']!=year or doc.get('url')!=links[str(year)]or doc.get('provider')!=PROVIDER or doc.get('format')!='audited_consolidated_PDF_book':_bad('supplement identity or publication invalid')
        raw=_native(doc['raw_receipt'],links[str(year)],3_000_000);parsed=_book(raw,year,deadline)
        if doc.get('sha256')!=sha256(raw).hexdigest():_bad('PDF original hash mismatch')
        books.append({**doc,'parsed_book_basis':parsed})
        for y,facts in parsed['facts'].items():
            if y in pdf_facts and not _same(pdf_facts[y],facts):_bad('audited book comparative conflict')
            pdf_facts[y]=facts;pdf_origins[y]={'supplement_filing_year':year,'pdf_sha256':doc['sha256'],
                'period_year':int(y),'period_role':'current'if int(y)==year else'comparative','not_original_period_filing_time_evidence':int(y)!=year}
    if set(pdf_facts)!={str(y)for y in YEARS}:_bad('five PDF cash periods incomplete')
    primary={};comparatives={};templates={};projected_docs=[]
    for year,doc in zip(YEARS,docs):
        if (type(doc.get('year'))is not int or doc['year']!=year or doc.get('period_end')!=f'{year}-12-31'or doc.get('provider')!=PROVIDER
                or doc.get('url')!=api_url('BalanceSheet')or not isinstance(doc.get('components'),list)or len(doc['components'])!=3):_bad('annual MOPS document scope invalid')
        current={};prior={}
        for statement,part in zip(STATEMENTS,doc['components']):
            if (part.get('statement')!=statement or type(part.get('year'))is not int or part['year']!=year or part.get('period_end')!=f'{year}-12-31'
                    or part.get('provider')!=PUBLIC_PROVIDER or part.get('url')!=api_url(statement)or not _same(part.get('request'),payload('2610',year))):_bad('MOPS annual component invalid')
            key=json.dumps(part['unit_template_receipt'],sort_keys=True)
            if key not in templates:templates[key]=_native(part['unit_template_receipt'],template_url(statement))
            raw=_native(part['raw_receipt'],api_url(statement))
            if part.get('sha256')!=sha256(raw).hexdigest():_bad('MOPS original hash mismatch')
            parsed=parse_statement(raw,'2610',year,statement,templates[key],include_prior=year>2021,allow_missing_intangible=True)
            if parsed['company_abbreviation']!='華航':_bad('MOPS issuer mismatch')
            current.update(parsed[year]);prior.update(parsed[year-1])
        for y,facts in [(year,current),*([(year-1,prior)]if year>2021 else[])]:
            if not set(FIELDS)-{INTANGIBLE}<=set(facts)<=set(FIELDS):_bad('only intangible purchase may be supplemented')
            for tag,value in pdf_facts[str(y)].items():
                if tag!=INTANGIBLE or tag in facts:
                    if facts.get(tag)!=value:_bad('MOPS and audited same-year cash conflict')
                facts[tag]=value
        primary[year]=current
        if year>2021:comparatives[year-1]=prior
        binding=pdf_origins[str(year)];digest=sha256(';'.join([p['sha256']for p in doc['components']]+[binding['pdf_sha256']]).encode()).hexdigest()
        projected_docs.append({**doc,'sha256':digest,'intangible_purchase_basis':binding})
    resolved,revisions=reconcile_comparative_rows(primary,comparatives)
    return {**assemble_annual_histories(resolved,expected_years=YEARS),'schema':'ordinary_consolidated_annual_history.v1','ticker':TICKER,'currency':'TWD','report_scope':'consolidated',
            'source_url':SOURCE_URL,'source_basis':POLICY,'source_origin_note':NOTE,'issuer_anchor':identity,
            **{k:deepcopy(original[k])for k in('issuer_master_receipt','published_annual_index_receipt','issuer_ir_index_receipt')},
            'documents':projected_docs,'supplement_documents':books,'comparative_revisions':revisions}

def _current_originals(value):
    observed=time.time()
    if not current_at(value['issuer_master_receipt'],observed):return False
    receipts=[value['published_annual_index_receipt'],value['issuer_ir_index_receipt']]
    receipts.extend(d['raw_receipt']for d in value['supplement_documents'])
    for doc in value['documents']:
        for part in doc['components']:
            receipts.extend((part['raw_receipt'],part['unit_template_receipt']))
    return all(current_at(r,observed)for r in receipts)

def project_bridge_history(value,ticker,*,deadline=None):
    try:
        if not isinstance(value,dict)or ticker!=TICKER:return None
        rebuilt=_project(value,deadline=deadline)
        if deadline is not None and time.monotonic()>=deadline:raise SourceResponseError('timeout')
        return rebuilt if _same(value,rebuilt)else None
    except (KeyError,ValueError,TypeError,OverflowError,AttributeError,OSError,EOFError,zlib.error,SourcePdfError,SourceResponseError):return None

def fetch_bridge_histories(ticker,*,transport=None):
    if not supports_bridge(ticker):_bad('unsupported issuer or current complete annual period')
    http=transport or BridgeHttp();batch=getattr(http,'batch',None)
    with batch()if callable(batch)else nullcontext():
        master,mr=fetch_master(http);parse_master(master,source_url=mr.get('source_url'))
        index,ir=http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':'2610'})
        if sorted(_filing_urls(index,'2610'))[-5:]!=YEARS:_bad('published five annual periods changed')
        templates={s:http.request(template_url(s))for s in STATEMENTS}
        for s,(raw,_)in templates.items():_template(raw,s)
        docs=[]
        for year in YEARS:
            parts=[]
            for s in STATEMENTS:
                raw,p=http.request(api_url(s),json_body=payload('2610',year))
                parsed=parse_statement(raw,'2610',year,s,templates[s][0],include_prior=year>2021,allow_missing_intangible=True)
                if parsed['company_abbreviation']!='華航':_bad('MOPS issuer mismatch')
                parts.append({'year':year,'period_end':f'{year}-12-31','statement':s,'provider':PUBLIC_PROVIDER,'url':api_url(s),'request':payload('2610',year),'sha256':sha256(raw).hexdigest(),'raw_receipt':p,'unit_template_receipt':templates[s][1]})
            docs.append({'year':year,'period_end':f'{year}-12-31','provider':PROVIDER,'url':api_url('BalanceSheet'),'components':parts})
        raw,pub=http.request(IR_URL);links=parse_index(raw);books=[]
        for year in PDF_YEARS:
            url=links[str(year)];raw,p=http.request(url)
            books.append({'year':year,'url':url,'provider':PROVIDER,'format':'audited_consolidated_PDF_book','sha256':sha256(raw).hexdigest(),'raw_receipt':p})
        value=_project({'issuer_master_receipt':mr,'published_annual_index_receipt':ir,'issuer_ir_index_receipt':pub,'documents':docs,'supplement_documents':books},deadline=http.deadline,acquiring=True)
    if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
    read_master(mr,lambda r,u:_native(r,u,2_500_000),max_age=1800)
    if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
    if not _current_originals(value):raise SourceResponseError('original_expired')
    return value

def fetch_bridge_result(ticker,*,transport=None):
    from source_audit import audited_fetch
    http=transport or BridgeHttp();errors=[]
    def acquire():
        try:return fetch_bridge_histories(ticker,transport=http)
        except (FilingError,SourceResponseError,SourcePdfError)as e:errors.append(e);raise
        except Exception as e:
            errors.append(e)
            # Receipt/expiry/archive failures cannot restart this entire batch.
            raise FilingError('China Airlines acquisition failed closed: '+type(e).__name__)from e
    result=audited_fetch('financial_statements',PROVIDER,acquire,default=None,record_counter=lambda v:len(v['years']),
                         success_message='華航五年合併九項科目由MOPS與官方查核現金流原件交叉核對；比較期、翻譯及補充科目來源逐項保留。')
    sent=sum(c.get('http_request_sent')is True for c in http.components)
    result['audit'].update(http_request_sent=bool(sent),http_request_count=sent,event_kind='aggregate'if sent else'local_block',component_statuses={str(i):deepcopy(c)for i,c in enumerate(http.components)},source_mix=POLICY)
    if isinstance(result.get('value'),dict):
        value=result['value']
        bodies=[p['raw_receipt']for d in value['documents']for p in d['components']]+[d['raw_receipt']for d in value['supplement_documents']]
        result['audit'].update(body_audit(bodies,http.components))
        result['audit'].update({k:deepcopy(result['value'][k])for k in('source_basis','source_origin_note','issuer_anchor','issuer_master_receipt','published_annual_index_receipt','issuer_ir_index_receipt','supplement_documents')})
    if http.components:result['audit']['http_status']=http.components[-1].get('http_status')
    if errors:result['audit']['error_kind']=getattr(errors[-1],'error_kind',type(errors[-1]).__name__)
    return result
