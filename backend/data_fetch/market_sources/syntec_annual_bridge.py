"""One exact issuer's audited book plus public filings provide five full periods.

The generic five-year, currency, nine-fact, comparison and PDF rules remain.
The book is a separate bounded profile; it never masquerades as a JSON filing.
"""
from copy import deepcopy
from contextlib import nullcontext
from datetime import date,datetime
from hashlib import sha256
import json,math,time,zlib
from zoneinfo import ZoneInfo
from .syntec_annual_transport import (BridgeHttp,PROVIDER,CATALOG,FORM,FORM_BODY,ROSTER_URL,PDF,CACHED_MASTER_KIND,CACHED_NATIVE_MASTER_KIND,NATIVE_MASTER_CACHE,CACHE_ONLY_FIELDS,parse_catalog,parse_download)
from .syntec_audited_book import parse_audited_book,LEGAL
from .mops_public_annual import STATEMENTS,api_url,template_url,payload,parse_statement,_template,_receipt as _public_receipt
from .official_xbrl_financial import FIELDS,INDEX_URL,FilingError,_filing_urls,assemble_annual_histories,reconcile_comparative_rows
from official_response_evidence import read_response
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError
TICKER='7750.TW';UBN='89660813';SOURCE_URL=CATALOG
POLICY='syntec-audited2022-book-and-public2023to2025.v1'
YEARS=[2021,2022,2023,2024,2025]
PUBLIC_PROVIDER='TWSE MOPS public annual JSON'
def supports_bridge(ticker):return ticker==TICKER and date.today().year==2026
def validate_bridge_context(data,ticker):
    if ticker!=TICKER:return
    context=data.get('company_identity',{})
    if context is None:context={}
    if not isinstance(context,dict):raise ValueError('annual_bridge_identity_invalid')
    for key,expected in [('ticker',TICKER),('stock_id','7750'),('official_name','新代'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if context.get(key)not in(None,'',expected):raise ValueError('annual_bridge_identity_conflict')
    if any(data.get(k)not in(None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType')):raise ValueError('annual_bridge_instrument_conflict')
    bad=context.get('forbidden_aliases',[])
    if not isinstance(bad,(list,tuple))or any(not isinstance(v,str)for v in bad)or {'新代',LEGAL,'syntec'}&{s.strip().casefold()for s in bad}:raise ValueError('annual_bridge_forbidden_issuer')
def _same(a,b):return json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False)==json.dumps(b,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _receipt(p,url,limit=250000,*,not_before=0):
    if (not isinstance(p,dict)or any(k in p for k in CACHE_ONLY_FIELDS)
            or 'http_status_observed'in p and p['http_status_observed']is not True
            or 'http_request_sent'in p and p['http_request_sent']is not True
            or 'cache_hit'in p and p['cache_hit']is not False
            or 'stale'in p and p['stale']is not False):raise FilingError('Syntec native receipt contradicts observed HTTP')
    return _public_receipt(p,url,limit,not_before=not_before)
def _master(p,today):
    cached=isinstance(p,dict)and p.get('evidence_kind')in(CACHED_MASTER_KIND,CACHED_NATIVE_MASTER_KIND)
    if cached:
        if (p.get('status')!='archived'or p.get('source_url')!=ROSTER_URL or p.get('http_status')is not None or p.get('http_status_observed')is not False
                or p.get('cache_source')!=('official-company-roster:v2:.TW'if p['evidence_kind']==CACHED_MASTER_KIND else NATIVE_MASTER_CACHE)or p.get('source_payload_sha256')!=p.get('raw_response_sha256')
                or type(p.get('source_payload_bytes'))is not int or p['source_payload_bytes']!=p.get('raw_response_bytes')
                or type(p.get('retrieved_at'))not in(int,float)or not math.isfinite(p['retrieved_at'])or not 0<p['retrieved_at']<=time.time()
                or type(p.get('raw_response_bytes'))is not int or not 0<p['raw_response_bytes']<=2_500_000):raise FilingError('Syntec cached issuer original invalid')
        if p['evidence_kind']==CACHED_NATIVE_MASTER_KIND:
            read_at,until=p.get('cache_verified_at_epoch'),p.get('cache_fresh_until_epoch');stamp=p['retrieved_at']
            if (type(read_at)not in(int,float)or type(until)not in(int,float)or not math.isfinite(read_at)or not math.isfinite(until)
                    or not stamp<=read_at<=time.time()or not read_at<until or not 0<until-stamp<=1801 or read_at-stamp>1800):
                raise FilingError('Syntec native cached original TTL at use unverified')
        raw=read_response(p)
        if len(raw)!=p['raw_response_bytes']:raise FilingError('Syntec cached issuer original size invalid')
    else:raw=_receipt(p,ROSTER_URL,2_500_000)
    from .official_company_legal_name import parse_roster,select_legal_name
    a=select_legal_name(parse_roster(raw,'.TW'),TICKER,'新代',today=today);rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='7750']
    if not a or len(rows)!=1:raise FilingError('Syntec issuer not unique')
    r=rows[0]
    if (a['legal_name']!=LEGAL or r.get('營利事業統一編號')!=UBN or r.get('英文簡稱')!='Syntec'or r.get('網址')!='https://www.syntecclub.com'
            or date.fromisoformat(a['as_of'])>datetime.fromtimestamp(p['retrieved_at'],ZoneInfo('Asia/Taipei')).date()):raise FilingError('Syntec issuer identity unverified')
    return {'ticker':TICKER,'legal_name':LEGAL,'official_name':'新代','official_ubn':UBN,'english_alias':'Syntec','registered_website':'https://www.syntecclub.com','master_as_of':a['as_of'],'master_response_sha256':sha256(raw).hexdigest()}
def _basis():
    return {'schema':'syntec-audited-book-first-comparative.v1','period_year':2021,'source_filing_year':2022,
            'facts_origin':'explicit_prior_period_in_published_audited_consolidated_book','no_separate2021_primary_filing_claimed':True}
def bridge_origin_note(value):
    if (not isinstance(value,dict)or value.get('ticker')!=TICKER or value.get('source_basis')!=POLICY or value.get('source_url')!=SOURCE_URL
            or value.get('years')!=[str(y)for y in YEARS]or not isinstance(value.get('documents'),list)or len(value['documents'])!=4):return None
    basis=value['documents'][0].get('first_period_basis')
    if not isinstance(basis,dict)or type(basis.get('period_year'))is not int or type(basis.get('source_filing_year'))is not int or not _same(basis,_basis()):return None
    return '2021、2022年度採證交所公開下載的新代2022年度查核合併財報，2021為原件明示的比較年度，未宣稱另有2021原始合併申報；2023至2025採MOPS公開三表，較新比較欄修訂保留。自由現金流沿同年營業現金流加帶符號設備及無形資產支出計算。'
def _book(raw,deadline):
    remaining=10 if deadline is None else min(10,deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    v=parse_audited_book(raw,timeout_seconds=remaining)
    return {**v,'facts':{str(y):r for y,r in v['facts'].items()}}
def project_bridge_history(value,ticker,*,deadline=None):
    try:
        if (not isinstance(value,dict)or ticker!=TICKER or value.get('ticker')!=ticker or value.get('source_basis')!=POLICY
                or value.get('schema')!='ordinary_consolidated_annual_history.v1'or value.get('currency')!='TWD'or value.get('report_scope')!='consolidated'
                or value.get('source_url')!=SOURCE_URL or value.get('years')!=[str(y)for y in YEARS]
                or not isinstance(value.get('documents'),list)or len(value['documents'])!=4):return None
        latest_close=datetime(2026,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        identity=_master(value['issuer_master_receipt'],datetime.now(ZoneInfo('Asia/Taipei')).date())
        if not _same(identity,value.get('issuer_anchor')):return None
        index=_receipt(value['published_annual_index_receipt'],INDEX_URL,2_500_000,not_before=latest_close)
        if sorted(_filing_urls(index,'7750'))!=[2023,2024,2025]:return None
        doc=value['documents'][0]
        if (not isinstance(doc,dict)or type(doc.get('year'))is not int or doc['year']!=2022 or doc.get('period_end')!='2022-12-31'
                or doc.get('provider')!=PROVIDER or doc.get('format')!='audited_consolidated_PDF_book'or not _same(doc.get('first_period_basis'),_basis())):return None
        cat=parse_catalog(_receipt(doc['published_catalog_receipt'],CATALOG,150000,not_before=latest_close))
        form_receipt=doc['download_form_receipt'];form=_receipt(form_receipt,FORM,150000,not_before=latest_close)
        url=parse_download(form,form_receipt)
        if doc.get('url')!=url or doc.get('download_request')!=FORM_BODY:return None
        raw=_receipt(doc['raw_receipt'],url,4_000_000,not_before=form_receipt['retrieved_at'])
        if len(raw)!=cat['declared_bytes']or doc.get('sha256')!=sha256(raw).hexdigest()or not _same(doc.get('catalog_binding'),cat):return None
        book=_book(raw,deadline)
        if not _same(doc.get('parsed_book_basis'),book):return None
        primary={int(y):r for y,r in book['facts'].items()};comparatives={};templates={}
        for year,doc in zip([2023,2024,2025],value['documents'][1:]):
            if (not isinstance(doc,dict)or type(doc.get('year'))is not int or doc['year']!=year or doc.get('period_end')!=f'{year}-12-31'
                    or doc.get('provider')!=PUBLIC_PROVIDER or doc.get('url')!=api_url('BalanceSheet')or not isinstance(doc.get('components'),list)or len(doc['components'])!=3):return None
            facts={};prior={}
            for statement,part in zip(STATEMENTS,doc['components']):
                if (not isinstance(part,dict)or part.get('statement')!=statement or type(part.get('year'))is not int or part['year']!=year
                        or part.get('period_end')!=f'{year}-12-31'or part.get('provider')!=PUBLIC_PROVIDER or part.get('url')!=api_url(statement)
                        or not _same(part.get('request'),payload('7750',year))):return None
                receipt=part['unit_template_receipt'];key=json.dumps(receipt,sort_keys=True)
                if key not in templates:templates[key]=_receipt(receipt,template_url(statement),not_before=latest_close)
                body=_receipt(part['raw_receipt'],api_url(statement),not_before=latest_close)
                if part.get('sha256')!=sha256(body).hexdigest():return None
                parsed=parse_statement(body,'7750',year,statement,templates[key],include_prior=True)
                if parsed['company_abbreviation']!='新代':return None
                facts.update(parsed[year]);prior.update(parsed[year-1])
            if set(facts)!=set(FIELDS)or set(prior)!=set(FIELDS)or doc.get('sha256')!=sha256(';'.join(p['sha256']for p in doc['components']).encode()).hexdigest():return None
            primary[year]=facts;comparatives[year-1]=prior
        resolved,revisions=reconcile_comparative_rows(primary,comparatives);projected=assemble_annual_histories(resolved,expected_years=YEARS)
        if (not _same(value.get('comparative_revisions'),revisions)or any(not _same(value.get(k),v)for k,v in projected.items())
                or bridge_origin_note(value)!=value.get('source_origin_note')):return None
        if deadline is not None and time.monotonic()>=deadline:raise SourceResponseError('timeout')
        return deepcopy(value)
    except (KeyError,ValueError,TypeError,OverflowError,AttributeError,OSError,EOFError,zlib.error,SourcePdfError):return None
def fetch_bridge_histories(ticker,*,transport=None):
    if not supports_bridge(ticker):raise FilingError('Syntec annual bridge market or current complete period unsupported')
    http=transport or BridgeHttp();batch=getattr(http,'batch',None)
    with batch()if callable(batch)else nullcontext():
        master,master_receipt=http.request(ROSTER_URL);identity=_master(master_receipt,datetime.now(ZoneInfo('Asia/Taipei')).date())
        index,index_receipt=http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':'7750'})
        if sorted(_filing_urls(index,'7750'))!=[2023,2024,2025]:raise FilingError('Syntec audited bridge published annual index changed')
        catalog,catalog_receipt=http.request(CATALOG);cat=parse_catalog(catalog)
        form,form_receipt=http.request(FORM,request=FORM_BODY);url=parse_download(form,form_receipt)
        raw,pdf_receipt=http.request(url)
        if len(raw)!=cat['declared_bytes']:raise FilingError('Syntec complete PDF bytes differ from published size')
        book=_book(raw,http.deadline);primary={int(y):r for y,r in book['facts'].items()};comparatives={}
        docs=[{'year':2022,'period_end':'2022-12-31','provider':PROVIDER,'format':'audited_consolidated_PDF_book','url':url,'sha256':sha256(raw).hexdigest(),
               'published_catalog_receipt':catalog_receipt,'catalog_binding':cat,'download_form_receipt':form_receipt,'download_request':FORM_BODY,
               'raw_receipt':pdf_receipt,'parsed_book_basis':book,'first_period_basis':_basis()}]
        templates={s:http.request(template_url(s))for s in STATEMENTS}
        for s,(b,_)in templates.items():_template(b,s)
        for year in(2023,2024,2025):
            facts={};prior={};parts=[]
            for statement in STATEMENTS:
                body,receipt=http.request(api_url(statement),json_body=payload('7750',year))
                parsed=parse_statement(body,'7750',year,statement,templates[statement][0],include_prior=True)
                if parsed['company_abbreviation']!='新代':raise FilingError('Syntec public annual issuer mismatch')
                facts.update(parsed[year]);prior.update(parsed[year-1])
                parts.append({'year':year,'period_end':f'{year}-12-31','statement':statement,'provider':PUBLIC_PROVIDER,'url':api_url(statement),'request':payload('7750',year),'sha256':sha256(body).hexdigest(),'raw_receipt':receipt,'unit_template_receipt':templates[statement][1]})
            if set(facts)!=set(FIELDS)or set(prior)!=set(FIELDS):raise FilingError('Syntec all nine current and comparative facts incomplete')
            primary[year]=facts;comparatives[year-1]=prior
            docs.append({'year':year,'period_end':f'{year}-12-31','provider':PUBLIC_PROVIDER,'url':api_url('BalanceSheet'),'sha256':sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest(),'components':parts})
        resolved,revisions=reconcile_comparative_rows(primary,comparatives)
        value={**assemble_annual_histories(resolved,expected_years=YEARS),'ticker':TICKER,'schema':'ordinary_consolidated_annual_history.v1','currency':'TWD','report_scope':'consolidated','source_url':SOURCE_URL,
               'source_basis':POLICY,'issuer_anchor':identity,'issuer_master_receipt':master_receipt,'published_annual_index_receipt':index_receipt,'documents':docs,'comparative_revisions':revisions}
        value['source_origin_note']=bridge_origin_note(value)
        if project_bridge_history(value,ticker,deadline=http.deadline)is None:raise FilingError('Syntec bridge complete original projection invalid')
        if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
        return value
def fetch_bridge_result(ticker,*,transport=None):
    from source_audit import audited_fetch
    http=transport or BridgeHttp();errors=[]
    def acquire():
        try:return fetch_bridge_histories(ticker,transport=http)
        except Exception as e:errors.append(e);raise
    result=audited_fetch('financial_statements',PROVIDER,acquire,default=None,record_counter=lambda v:len(v['years']),
                         success_message='新代五年合併九科目由查核財報及公開三表完整原件核對；首年採明示比較欄，保留較新修訂與原現金流公式。')
    sent=sum(c.get('http_request_sent')is True for c in http.components)
    result['audit'].update(http_request_sent=bool(sent),http_request_count=sent,event_kind='aggregate'if sent else'local_block',component_statuses={str(i):deepcopy(c)for i,c in enumerate(http.components)},source_mix=POLICY)
    if isinstance(result.get('value'),dict):
        # Saving only filing documents loses the full issuer/index originals
        # needed to independently replay this mixed-source annual receipt.
        # The PDF is already retained once inside documents.
        result['audit'].update({k:deepcopy(result['value'][k])for k in
            ('source_basis','issuer_anchor','issuer_master_receipt','published_annual_index_receipt','source_origin_note')})
    if http.components:result['audit']['http_status']=http.components[-1].get('http_status')
    if errors:result['audit']['error_kind']=getattr(errors[-1],'error_kind',type(errors[-1]).__name__)
    return result
