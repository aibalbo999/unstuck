"""Full annual facts and comparatives from MOPS' anonymous public JSON UI.

JSON has no unit field. Its three exact official renderer contracts are bound
by full-byte fingerprints and receipts; changed templates fail closed.
"""
from copy import deepcopy
from contextlib import contextmanager,nullcontext
from datetime import date,datetime
from hashlib import sha256
import json,math,os,re,time,zlib
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo
import httpx

from official_response_evidence import archive_response,read_response
from external_http_client import proxy_url_for_request
from search_provider_runtime import cooldown_state,scope_key,remember_failure,observe_http_response,SourceResponseError
from .official_mopsfin_financial import STATEMENT_FIELDS,_amount
from .official_xbrl_financial import (FIELDS,INDEX_URL,FilingError,PROVIDER as OFFICIAL_XBRL_PROVIDER,
    _filing_urls,reconcile_comparative_rows,assemble_annual_histories)

PROVIDER='TWSE MOPS public annual JSON'
SOURCE_URL='https://mops.twse.com.tw/mops/#/web/t164sb03'
STATEMENTS={'BalanceSheet':'t164sb03','IncomeStatement':'t164sb04','CashflowStatement':'t164sb05'}
TEMPLATE_HASHES={'t164sb03':'6d1695de0f0234163792333a4cf07ef9316f01687ef1a0928fa6ddc9feecc7ba','t164sb04':'fbfd5754dd2ce843cadd7a800e188fc84acda6ee61bfb64d5afd3a1ac9cfee23','t164sb05':'4f2491487da3489f8cb5cb9acd95dd6ee73981ebbbb0c45e8df4c5e2bfc0b413'}
MAX_BYTES=250000
INTANGIBLE='PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'
PROPERTY='PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'
PURCHASE_TAGS={PROPERTY,INTANGIBLE}
INVESTING_HEADER='投資活動之現金流量'
INVESTING_TOTAL='投資活動之淨現金流入（流出）'
CASHFLOW_HEADERS={'營業活動之現金流量－間接法',INVESTING_HEADER,'籌資活動之現金流量'}
PROXY_ENV=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')

def api_url(statement):return 'https://mops.twse.com.tw/mops/api/'+STATEMENTS[statement]
def template_url(statement):return 'https://mops.twse.com.tw/mops/assets/'+STATEMENTS[statement]+'.js'
def payload(issuer,year):return {'companyId':issuer,'dataType':'2','season':'4','year':str(year-1911),'subsidiaryCompanyId':''}

def _object(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise FilingError('duplicate public MOPS JSON key')
        value[key]=item
    return value

def _template(raw,statement):
    if (not isinstance(raw,bytes)or len(raw)>MAX_BYTES
            or sha256(raw).hexdigest()!=TEMPLATE_HASHES[STATEMENTS[statement]]):
        raise FilingError('unverified MOPS public unit/calendar renderer contract')

def _reconciled_investing_cashflows(rows,periods):
    """Return exact investing-detail sums only for a complete, well-formed section."""
    headers=[i for i,row in enumerate(rows)if isinstance(row,list)and row and isinstance(row[0],str)
             and row[0].strip()==INVESTING_HEADER]
    if len(headers)!=1:raise FilingError('public MOPS investing section is missing or ambiguous')
    start=headers[0]
    header_row=rows[start]
    if len(header_row)!=3 or any(type(value)is not str for value in header_row[1:])or any(value.strip()for value in header_row[1:]):
        raise FilingError('public MOPS investing section header is malformed')
    ends=[i for i,row in enumerate(rows[start+1:],start+1)if isinstance(row,list)and row and isinstance(row[0],str)
          and row[0].strip()in CASHFLOW_HEADERS]
    end=ends[0]if ends else len(rows)
    totals=[i for i,row in enumerate(rows[start+1:end],start+1)if isinstance(row,list)and row and isinstance(row[0],str)
            and row[0].strip()==INVESTING_TOTAL]
    all_totals=[row for row in rows if isinstance(row,list)and row and isinstance(row[0],str)
                and row[0].strip()==INVESTING_TOTAL]
    if len(totals)!=1 or len(all_totals)!=1:raise FilingError('public MOPS investing total is missing or ambiguous')
    total_index=totals[0];sums={period:0 for period,_ in periods};reported={}
    if total_index!=end-1:raise FilingError('public MOPS investing total is not the final section row')
    if total_index<=start+1:raise FilingError('public MOPS investing detail section is empty')
    for row in rows[start+1:total_index]:
        if (not isinstance(row,list)or len(row)!=3 or not isinstance(row[0],str)
                or not row[0].strip()):
            raise FilingError('public MOPS investing detail row is malformed')
        label=row[0].strip()
        for period,col in periods:
            if type(row[col])is not str or len(row[col])>40:
                raise FilingError('public MOPS investing detail amount is invalid: '+label)
            sums[period]+=_amount(row[col],label=label)
    total_row=rows[total_index]
    if len(total_row)!=3:raise FilingError('public MOPS investing total columns are invalid')
    for period,col in periods:
        if type(total_row[col])is not str or len(total_row[col])>40:
            raise FilingError('public MOPS investing total amount is invalid')
        reported[period]=_amount(total_row[col],label=INVESTING_TOTAL)
        if sums[period]!=reported[period]:
            raise FilingError('public MOPS investing detail does not reconcile to reported net total')
    return sums

def parse_statement(raw,issuer,year,statement,template,*,include_prior=True,allow_missing_intangible=False,
                    allow_reconciled_missing_purchases=False):
    if (statement not in STATEMENTS or not re.fullmatch(r'[1-9]\d{3}',issuer)
            or type(year)is not int or not 2013<=year<date.today().year
            or not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES):
        raise FilingError('invalid public MOPS statement identity or body')
    _template(template,statement)
    try:
        value=json.loads(raw.decode('utf8',errors='strict'),object_pairs_hook=_object)
        result=value['result']
        if (type(value['code'])is not int or value['code']!=200 or not isinstance(result,dict)
                or result['reportType']!='合併'or result['year']!=str(year-1911)or result['season']!='4'
                or type(result['fiscalYear'])is not str or result['fiscalYear'].strip()
                or not isinstance(result['companyAbbreviation'],str)or not result['companyAbbreviation'].strip()
                or len(result['companyAbbreviation'])>100 or not isinstance(result.get('subsidiary'),list)
                or result.get('subsidiaryCompanyId','')!=''
                or any(k in result for k in ('currency','unit','scale'))):
            raise FilingError('public MOPS scope/period/unit metadata not verified')
        refs=[v['url']for v in result['urlList']if isinstance(v,dict)and v.get('name')=='XBRL資訊平台']
        if len(refs)!=1:raise FilingError('ambiguous public MOPS issuer reference')
        ref=urlsplit(refs[0]);q=parse_qs(ref.query,keep_blank_values=True)
        if (ref.scheme!='https'or ref.netloc!='mopsov.twse.com.tw'or ref.path!='/server-java/t164sb01'or ref.fragment
                or q!={'step':['1'],'CO_ID':[issuer],'SYEAR':[str(year)],'SSEASON':['4'],'REPORT_ID':['C']}):
            raise FilingError('public MOPS issuer reference mismatch')
        suffix='年12月31日'if statement=='BalanceSheet'else'年度'
        subs=[{'main':'金額','sub':[]}]+([]if statement=='CashflowStatement'else[{'main':'%','sub':[]}])
        expected=[{'main':'會計項目','sub':[]},{'main':str(year-1911)+suffix,'sub':subs},{'main':str(year-1912)+suffix,'sub':subs}]
        opening=expected+[{'main':str(year-1912)+'年01月01日','sub':subs}]
        if result['titles']!=expected and not (statement=='BalanceSheet'and result['titles']==opening):
            raise FilingError('public MOPS annual amount-column alignment mismatch')
        rows=result['reportList']
        if not isinstance(rows,list)or not 1<=len(rows)<=400:raise FilingError('public MOPS annual rows invalid')
        columns=(1,2)if statement=='CashflowStatement'else(1,3)
        width=3 if statement=='CashflowStatement'else 1+2*(len(result['titles'])-1)
        facts={year:{},year-1:{}};missing_purchases=[]
        for tag,label in STATEMENT_FIELDS[statement].items():
            matches=[row for row in rows if isinstance(row,list)and row and isinstance(row[0],str)and row[0].strip()==label]
            # Absence stays unknown. Only the complete five-year caller may
            # carry this one absent row to explicit later comparative facts.
            if not matches and allow_reconciled_missing_purchases and tag in PURCHASE_TAGS:
                missing_purchases.append(tag);continue
            if not matches and allow_missing_intangible and tag==INTANGIBLE:continue
            if len(matches)!=1:raise FilingError('missing or duplicate public MOPS fact: '+label)
            row=matches[0]
            if len(row)!=width:raise FilingError('public MOPS monetary columns invalid')
            for period,col in ((year,columns[0]),(year-1,columns[1])):
                if period==year-1 and not include_prior:continue
                if type(row[col])is not str or len(row[col])>40:raise FilingError('invalid public MOPS monetary value: '+label)
                number=_amount(row[col],label=label)
                if tag.startswith('PurchaseOf')and number>0:raise FilingError('public MOPS purchase sign is ambiguous: '+label)
                facts[period][tag]=number
        facts['company_abbreviation']=result['companyAbbreviation'].strip()
        if missing_purchases:
            if statement!='CashflowStatement'or not set(missing_purchases)<=PURCHASE_TAGS:
                raise FilingError('public MOPS missing purchase facts are ambiguous')
            periods=[(year,columns[0])]+([(year-1,columns[1])]if include_prior else [])
            try:
                # Explicit purchase rows with positive values fail above.
                # If every visible investing row exactly reconciles, the
                # missing purchase outflows have zero residual; each is
                # therefore zero under the same nonpositive cashflow rule.
                _reconciled_investing_cashflows(rows,periods)
            except FilingError:
                if not (allow_missing_intangible and missing_purchases==[INTANGIBLE]):raise
            else:
                recovered=[]
                for period,_ in periods:
                    for tag in missing_purchases:
                        facts[period][tag]=0
                        recovered.append({'period_year':period,'fact':tag,'value_twd':0,
                                          'filing_year':year,
                                          'proof':'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases'})
                facts['inferred_zero_facts']=sorted(recovered,key=lambda item:(item['period_year'],item['fact']))
        return facts
    except (KeyError,TypeError,ValueError,UnicodeError,IndexError)as exc:
        if isinstance(exc,FilingError):raise
        raise FilingError('public MOPS JSON metadata or fact format invalid')from exc

def _comparative_coverage(primary,comparatives,inferred_zero_facts=()):
    """Describe recovered comparisons and mark values proven by exact section totals."""
    coverage=[]
    for year,row in comparatives.items():
        missing=sorted(set(FIELDS)-set(row))
        item={'year':year,'comparative_filing_year':year+1,
              'status':'partial_nonconflicting'if missing else'complete',
              'available_facts':sorted(row),'missing_facts':missing,
              'retained_primary_facts':[tag for tag in missing if tag in primary[year]]}
        inferred=sorted({fact['fact']for fact in inferred_zero_facts
                         if fact['period_year']==year and fact['filing_year']==year+1})
        if inferred:item['inferred_zero_facts']=inferred
        coverage.append(item)
    return coverage

def _receipt(receipt,url,limit=MAX_BYTES,*,not_before=0):
    if (not isinstance(receipt,dict)or receipt.get('status')!='archived'or receipt.get('source_url')!=url
            or type(receipt.get('http_status'))is not int or receipt['http_status']!=200
            or type(receipt.get('retrieved_at'))not in (int,float)or not math.isfinite(receipt['retrieved_at'])
            or not 0<receipt['retrieved_at']<=time.time()or receipt['retrieved_at']<not_before
            or type(receipt.get('raw_response_bytes'))is not int or not 0<receipt['raw_response_bytes']<=limit
            or receipt.get('evidence_kind')!='raw_http_response_bytes'):
        raise FilingError('public MOPS raw receipt metadata invalid')
    try:raw=read_response(receipt)
    except (OSError,ValueError,EOFError,TypeError,zlib.error):raise FilingError('public MOPS original receipt cannot be read')from None
    if len(raw)!=receipt['raw_response_bytes']:raise FilingError('public MOPS original body length mismatch')
    return raw

def _first_period_basis(year):
    return {'schema':'mops-public-complete-first-comparative.v1','period_year':year,
            'source_filing_year':year+1,'facts_origin':'reported_prior_period_in_consolidated_filing',
            'no_primary_filing_for_first_period_claimed':True}

def _valid_first_period_basis(basis,year):
    return (isinstance(basis,dict)and type(basis.get('period_year'))is int
            and type(basis.get('source_filing_year'))is int and basis==_first_period_basis(year)
            and basis.get('no_primary_filing_for_first_period_claimed')is True)

def first_comparative_origin_note(value):
    """Describe the already-validated period origin without inventing a filing."""
    if not isinstance(value,dict):return None
    docs=value.get('documents');years=value.get('years')
    if not isinstance(docs,list)or len(docs)!=4 or not isinstance(years,list)or len(years)!=5:return None
    basis=docs[0].get('first_period_basis')if isinstance(docs[0],dict)else None
    if not isinstance(basis,dict):return None
    year=basis.get('period_year')
    if not _valid_first_period_basis(basis,year):return None
    return f'{year}年度採{year+1}年度官方合併財報明示的比較欄；四份合併年報提供完整五年數值，未宣稱另有{year}年度原始合併年報憑據。'

def project_public_history(value,ticker):
    """Re-extract full bytes, periods, unit contracts and comparatives at admission."""
    try:
        if not isinstance(value,dict):return None
        years=value['years'];docs=value['documents'];issuer=ticker.split('.')[0]
        if (value.get('ticker')!=ticker or not re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?',ticker)
                or value.get('schema')!='ordinary_consolidated_annual_history.v1'or value.get('currency')!='TWD'
                or value.get('report_scope')!='consolidated'or value.get('source_url')!=SOURCE_URL
                or not isinstance(years,list)or len(years)!=5 or any(type(y)is not str or not re.fullmatch(r'20\d{2}',y)for y in years)
                or years!=[str(y)for y in range(int(years[0]),int(years[0])+5)]or int(years[-1])>=date.today().year
                or not isinstance(docs,list)or len(docs)not in(4,5)):return None
        primary={};comparatives={};templates={};names=set();inferred_zero_facts=[]
        latest_close=datetime(int(years[-1])+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        comparative_start=len(docs)==4
        filing_years=years[1:]if comparative_start else years
        if comparative_start:
            if int(years[0])<2013:return None
            first=docs[0]
            if (not isinstance(first,dict)or not _valid_first_period_basis(first.get('first_period_basis'),int(years[0]))
                    or any(not isinstance(d,dict)or 'first_period_basis'in d or 'published_index_receipt'in d for d in docs[1:])):return None
            index=_receipt(first.get('published_index_receipt'),INDEX_URL,2_500_000,not_before=latest_close)
            if sorted(_filing_urls(index,issuer))!=[int(y)for y in filing_years]:return None
        elif any(not isinstance(d,dict)or 'first_period_basis'in d or 'published_index_receipt'in d for d in docs):return None
        for y,doc in zip(filing_years,docs):
            if not isinstance(doc,dict):return None
            year=int(y);parts=doc['components']
            if (type(doc['year'])is not int or doc['year']!=year or doc.get('period_end')!=y+'-12-31'
                    or doc.get('provider')!=PROVIDER or doc.get('url')!=api_url('BalanceSheet')
                    or not isinstance(parts,list)or len(parts)!=3):return None
            facts={};prior={}
            for statement,part in zip(STATEMENTS,parts):
                if not isinstance(part,dict):return None
                url=api_url(statement);tu=template_url(statement)
                if (part.get('statement')!=statement or type(part.get('year'))is not int or part['year']!=year
                        or part.get('period_end')!=y+'-12-31'or part.get('provider')!=PROVIDER or part.get('url')!=url
                        or part.get('request')!=payload(issuer,year)):return None
                close=datetime(year+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
                raw=_receipt(part['raw_receipt'],url,not_before=close)
                if sha256(raw).hexdigest()!=part.get('sha256'):return None
                receipt=part['unit_template_receipt'];key=json.dumps(receipt,sort_keys=True)
                if key not in templates:templates[key]=_receipt(receipt,tu,not_before=latest_close)
                parsed=parse_statement(raw,issuer,year,statement,templates[key],include_prior=year>int(years[0]),
                                       allow_missing_intangible=True,allow_reconciled_missing_purchases=True)
                names.add(parsed['company_abbreviation'])
                if len(names)!=1:return None
                facts.update(parsed[year]);prior.update(parsed[year-1])
                inferred_zero_facts.extend(parsed.get('inferred_zero_facts',[]))
            if doc.get('sha256')!=sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest():return None
            primary[year]=facts
            if year>int(years[0]):comparatives[year-1]=prior
        if comparative_start:
            first_year=int(years[0]);first_facts=comparatives.get(first_year)
            if not isinstance(first_facts,dict)or set(first_facts)!=set(FIELDS):return None
            primary={first_year:deepcopy(first_facts),**primary}
        inferred_zero_facts=sorted(inferred_zero_facts,key=lambda item:(item['period_year'],item['fact'],item['filing_year']))
        resolved,revisions=reconcile_comparative_rows(primary,comparatives)
        projected=assemble_annual_histories(resolved,expected_years=list(primary))
        coverage=_comparative_coverage(primary,comparatives,inferred_zero_facts)
        if ('comparative_coverage'in value and
                json.dumps(value['comparative_coverage'],sort_keys=True)!=json.dumps(coverage,sort_keys=True)):return None
        rows=value.get('raw_twd_by_year')
        if (not isinstance(rows,dict)or set(rows)!=set(years)
                or any(not isinstance(r,dict)or set(r)!=set(FIELDS.values())|{'free_cash_flow'}
                       or any(type(n)is not int for n in r.values())for r in rows.values())):return None
        for k in projected:
            if k in {'years','raw_twd_by_year'}:continue
            values=value.get(k)
            if not isinstance(values,list)or len(values)!=5 or any(type(n)not in (int,float)or not math.isfinite(n)for n in values):return None
        if ('inferred_zero_facts'in value and
                json.dumps(value['inferred_zero_facts'],sort_keys=True)!=json.dumps(inferred_zero_facts,sort_keys=True)):
            return None
        if inferred_zero_facts and 'inferred_zero_facts'not in value:return None
        if (any(projected[k]!=value.get(k)for k in projected)
                or json.dumps(revisions,sort_keys=True)!=json.dumps(value.get('comparative_revisions'),sort_keys=True)):return None
        return {**deepcopy(value),'comparative_coverage':coverage,'inferred_zero_facts':inferred_zero_facts}
    except (KeyError,ValueError,TypeError,OverflowError):return None

class PublicMopsHttp:
    """Operation-local connections; no cookies, retries or renewed body cache."""
    def __init__(self,*,client_factory=None,seconds=45):
        self.factory=client_factory;self.deadline=time.monotonic()+seconds;self.components=[]
        self._batch_active=False;self._client=None;self.individual_downloads=False

    @contextmanager
    def batch(self):
        """Share only TCP/TLS inside one complete query, then always close it."""
        if self._batch_active:raise FilingError('public MOPS transport batch is already active')
        self._batch_active=True
        try:yield self
        finally:
            client=self._client;self._client=None;self._batch_active=False
            if client is not None:
                try:client.cookies.clear()
                finally:client.close()

    @contextmanager
    def _request_client(self,timeout):
        factory=self.factory or httpx.Client
        if not self._batch_active:
            with factory(timeout=timeout,follow_redirects=False,trust_env=False)as client:
                client.cookies.clear()
                try:yield client
                finally:client.cookies.clear()
            return
        if self._client is None:
            self._client=factory(timeout=timeout,follow_redirects=False,trust_env=False)
        # Response cookies never become another query's application session.
        self._client.cookies.clear()
        try:yield self._client
        finally:self._client.cookies.clear()

    def request(self,url,*,request=None,json_body=None):
        urls={api_url(s)for s in STATEMENTS}|{template_url(s)for s in STATEMENTS}|{INDEX_URL}
        individual=False
        if self.individual_downloads:
            from .ordinary_individual_annual import individual_url
            individual=individual_url(url)
        if url not in urls and not individual:raise FilingError('public MOPS transport URL invalid')
        diag={'url':url,'http_request_sent':False};self.components.append(diag)
        limit=6000000 if individual else 2500000 if url==INDEX_URL else MAX_BYTES
        if self.factory is None and os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise FilingError('network is disabled for tests')
        if proxy_url_for_request(url,PROVIDER)or any(os.getenv(k)for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        host=urlsplit(url).hostname;key=scope_key(PROVIDER,endpoint=host)
        # Honor the actual research transport's existing host cooldown too.
        hosts={host,'mops.twse.com.tw'}if url==INDEX_URL else{host}
        if any(cooldown_state(scope_key(p,endpoint=h))for h in hosts for p in (PROVIDER,'Verified issuer news')):raise SourceResponseError('cooldown')
        remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:raise SourceResponseError('timeout')
        stop=time.monotonic()+remaining;timeout=httpx.Timeout(remaining,connect=min(2.,remaining))
        method='POST'if request is not None or json_body is not None else'GET'
        diag.update(request_method=method)
        try:
            with self._request_client(timeout)as client:
                kwargs={'json':json_body}if json_body is not None else{'data':request}if request is not None else{}
                diag['http_request_sent']=True
                with client.stream(method,url,headers={'Accept':'application/json'if json_body is not None else'*/*'},timeout=timeout,**kwargs)as response:
                    observe_http_response(response);diag.update(http_status=response.status_code)
                    if response.status_code!=200:
                        exc=SourceResponseError({401:'authentication',403:'access_denied',429:'rate_limited'}.get(response.status_code,'server_error'if response.status_code>=500 else'http_error'),status_code=response.status_code)
                        exc.response=response
                        if response.status_code in {401,403,429}or response.status_code>=500:remember_failure(key,exc)
                        raise exc
                    raw=b''
                    for chunk in response.iter_bytes():
                        raw+=chunk
                        if len(raw)>limit:raise SourceResponseError('response_too_large')
                        if time.monotonic()>=stop:raise SourceResponseError('timeout')
                    ctype=response.headers.get('content-type','').split(';')[0].strip().lower()
            types={'application/json'}if json_body is not None else{'text/html','application/xhtml+xml'}if url==INDEX_URL else{'text/javascript','application/javascript'}
            if individual:
                types={'application/xml','text/xml','application/xhtml+xml','text/html','application/octet-stream',''}
                if not raw.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'<?xml'):raise SourceResponseError('parse_error')
            if ctype not in types:raise SourceResponseError('unexpected_content_type')
            if time.monotonic()>=stop or time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
            try:receipt=archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)
            except (OSError,ValueError,EOFError,zlib.error):raise FilingError('public MOPS native body archive unavailable')from None
            if _receipt(receipt,url,limit)!=raw:raise FilingError('public MOPS archive failed')
            diag.update(response_sha256=sha256(raw).hexdigest(),response_bytes=len(raw),status='complete')
            return raw,receipt
        except httpx.HTTPError as exc:
            diag.update(error_kind='timeout'if isinstance(exc,httpx.TimeoutException)else'transport_error')
            raise SourceResponseError(diag['error_kind'])from exc
        except Exception as exc:
            diag.update(error_kind=getattr(exc,'error_kind',type(exc).__name__));raise

def fetch_public_annual_histories(ticker,*,transport=None):
    if not isinstance(ticker,str)or not re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?',ticker):raise FilingError('invalid public MOPS annual ticker')
    http=transport or PublicMopsHttp();batch=getattr(http,'batch',None)
    with batch()if callable(batch)else nullcontext():
        value=_fetch_public_annual_histories(ticker,http)
    if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
    return value

def _fetch_public_annual_histories(ticker,http,*,index_original=None):
    issuer=ticker.split('.')[0]
    index,index_receipt=index_original if index_original is not None else http.request(INDEX_URL,request={'step':'1','firstin':'ture','off':'1','queryName':'co_id','inpuType':'co_id','TYPEK':'all','co_id':issuer})
    urls=_filing_urls(index,issuer);years=sorted(urls)[-5:]
    comparative_start=len(years)==4 and years[0]>2013
    if len(years)not in(4,5)or(len(years)==4 and not comparative_start)or years!=list(range(years[0],years[0]+len(years)))or years[-1]>=date.today().year:raise FilingError('fewer than five contiguous published consolidated annual filings')
    templates={s:http.request(template_url(s))for s in STATEMENTS}
    for s,(raw,_)in templates.items():_template(raw,s)
    primary={};comparatives={};docs=[];names=set();inferred_zero_facts=[]
    for year in years:
        facts={};prior={};parts=[]
        for s in STATEMENTS:
            url=api_url(s);body,receipt=http.request(url,json_body=payload(issuer,year))
            parsed=parse_statement(body,issuer,year,s,templates[s][0],include_prior=comparative_start or year>years[0],
                                   allow_missing_intangible=True,allow_reconciled_missing_purchases=True)
            facts.update(parsed[year]);prior.update(parsed[year-1]);inferred_zero_facts.extend(parsed.get('inferred_zero_facts',[]))
            names.add(parsed['company_abbreviation'])
            if len(names)!=1:raise FilingError('public MOPS company abbreviation inconsistent across annual documents')
            parts.append({'year':year,'period_end':f'{year}-12-31','statement':s,'provider':PROVIDER,'url':url,'request':payload(issuer,year),'sha256':sha256(body).hexdigest(),'raw_receipt':receipt,'unit_template_receipt':templates[s][1]})
        primary[year]=facts
        if comparative_start or year>years[0]:comparatives[year-1]=prior
        docs.append({'year':year,'period_end':f'{year}-12-31','provider':PROVIDER,'url':api_url('BalanceSheet'),'sha256':sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest(),'components':parts})
    if comparative_start:
        first_year=years[0]-1;first_facts=comparatives[first_year]
        if set(first_facts)!=set(FIELDS):raise FilingError('annual XBRL facts are incomplete for '+str(first_year))
        primary={first_year:deepcopy(first_facts),**primary};years=[first_year,*years]
        docs[0]['first_period_basis']=_first_period_basis(first_year)
        docs[0]['published_index_receipt']=index_receipt
    resolved,revisions=reconcile_comparative_rows(primary,comparatives)
    inferred_zero_facts=sorted(inferred_zero_facts,key=lambda item:(item['period_year'],item['fact'],item['filing_year']))
    value={**assemble_annual_histories(resolved,expected_years=years),'ticker':ticker,'currency':'TWD','schema':'ordinary_consolidated_annual_history.v1','report_scope':'consolidated','source_url':SOURCE_URL,'documents':docs,'comparative_revisions':revisions,'comparative_coverage':_comparative_coverage(primary,comparatives,inferred_zero_facts),'inferred_zero_facts':inferred_zero_facts}
    if project_public_history(value,ticker)is None:raise FilingError('public MOPS original history projection invalid')
    if time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
    return value

def fetch_public_financial_result(ticker,*,transport=None):
    from .mops_public_gap_cache import fetch_cached_public_result
    return fetch_cached_public_result(ticker, transport=transport)


def _fetch_public_financial_result_uncached(ticker,*,transport=None):
    from source_audit import audited_fetch
    http=transport or PublicMopsHttp();errors=[];fallback={'attempted':False,'requests':[]}
    def eligible_xbrl_fallback(exc):
        if not isinstance(exc,SourceResponseError)or exc.status_code in {401,403,429}:
            return False
        status=exc.status_code
        transport_failure=status is None and exc.error_kind in {'timeout','transport_error'}
        server_failure=type(status)is int and 500<=status<600 and exc.error_kind=='server_error'
        if not (transport_failure or server_failure):return False
        indexed=any(component.get('url')==INDEX_URL and component.get('http_status')==200
                    for component in http.components if isinstance(component,dict))
        failed_document=any(
            component.get('url')!=INDEX_URL and component.get('http_request_sent')is True
            and ((component.get('http_status')is None and component.get('error_kind')in {'timeout','transport_error'})
                 or (type(component.get('http_status'))is int and 500<=component['http_status']<600
                     and component.get('error_kind')=='server_error'))
            for component in http.components if isinstance(component,dict))
        return indexed and failed_document
    def acquire():
        try:return fetch_public_annual_histories(ticker,transport=http)
        except Exception as exc:
            if not isinstance(exc,(FilingError,SourceResponseError)):
                exc=FilingError('public MOPS acquisition failed closed: '+type(exc).__name__)
            errors.append(exc)
            if not eligible_xbrl_fallback(exc):raise exc
            fallback['attempted']=True
            try:
                from provider_resilience import call_provider_with_resilience
                from . import official_xbrl_financial as xbrl_source
                value=call_provider_with_resilience(
                    OFFICIAL_XBRL_PROVIDER,
                    lambda:xbrl_source.fetch_official_annual_histories(ticker,request_observer=fallback['requests'].append),
                )
                from data_fetch.annual_financial_source_provider import ordinary_projection
                if ordinary_projection(value,ticker)is None:
                    raise FilingError('official XBRL fallback failed annual projection')
                return {**value,'ticker':ticker,'currency':'TWD','schema':'ordinary_consolidated_annual_history.v1','report_scope':'consolidated'}
            except Exception as fallback_error:
                errors.append(fallback_error)
                fallback['error_kind']=getattr(fallback_error,'error_kind',type(fallback_error).__name__)
                raise
    result=audited_fetch('financial_statements',PROVIDER,acquire,default=None,record_counter=lambda v:len(v['years']),success_message='五年官方JSON合併年度必要科目及可得比較值已核對；缺列僅由明示較新比較值補齊，無衝突的不完整比較期保留已明示原年度值。')
    audit=result['audit'];sent=sum(c.get('http_request_sent')is True for c in http.components)
    xbrl_sent=sum(c.get('http_request_sent')is True for c in fallback['requests'])
    components={str(i):deepcopy(c)for i,c in enumerate(http.components)}
    if fallback['attempted']:
        components['xbrl_fallback']=deepcopy(fallback['requests'])
        audit.update(provider=OFFICIAL_XBRL_PROVIDER,actual_provider=OFFICIAL_XBRL_PROVIDER,
                     source_mix='official_xbrl_after_public_json_transport_failure',
                     fallback_status='error'if fallback.get('error_kind')else'success')
        if audit.get('status')=='success':
            recovered=(result.get('value')or{}).get('recovered_documents')or[]
            if recovered:
                audit.update(actual_provider=OFFICIAL_XBRL_PROVIDER+' + TWSE MOPS official financial comparison',
                             source_mix='official_xbrl_after_public_json_transport_failure_with_official_comparison_recovery')
            audit['message']='公開 JSON 文件暫時無法傳輸；已切換官方合併 iXBRL，完成五年必要科目與原件核對。'
            if recovered:audit['message']+='；個別 iXBRL 原件暫時無法讀取的年度另以官方財務比較資料恢復。'
    audit.update(http_request_sent=bool(sent+xbrl_sent),http_request_count=sent+xbrl_sent,
                 event_kind='aggregate'if sent+xbrl_sent else'local_block',component_statuses=components)
    if fallback['requests'] and 'http_status'in fallback['requests'][-1]:audit['http_status']=fallback['requests'][-1]['http_status']
    elif http.components:audit['http_status']=http.components[-1].get('http_status')
    if errors and audit.get('status')!='success':audit['error_kind']=getattr(errors[-1],'error_kind',type(errors[-1]).__name__)
    return result
