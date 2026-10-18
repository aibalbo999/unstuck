"""Ordinary fixed public MOPS routes for one audited-book annual bridge."""
from hashlib import sha256
import base64,json,math,os,re,time
from urllib.parse import urlsplit,urljoin
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .mops_public_annual import PublicMopsHttp,api_url,template_url,STATEMENTS,INDEX_URL,PROXY_ENV
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL
from official_response_evidence import archive_response,read_response
from bounded_curl_process import collect_capped_process
from company_conference_transport import _headers
from external_http_client import proxy_url_for_request
from search_provider_runtime import SourceResponseError,scope_key,cooldown_state,remember_failure,observe_http_response
from .official_xbrl_financial import FilingError
import httpx
PROVIDER='TWSE MOPS Syntec audited annual bridge'
FORM='https://doc.twse.com.tw/server-java/t57sb01'
CATALOG=FORM+'?co_id=7750&colorchg=1&mtype=A&seamon=&step=1&year=111'
NAME='202204_7750_AI1.pdf'
PDF=re.compile(r'https://doc\.twse\.com\.tw/pdf/202204_7750_AI1_(20\d{6})_(\d{6})\.pdf\Z')
FORM_BODY={'colorchg':'1','step':'9','kind':'A','co_id':'7750','filename':NAME,'DEBUG':''}
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
CACHED_NATIVE_MASTER_KIND='cached_issuer_news_raw_verified_by_payload.v1'
NATIVE_MASTER_CACHE='issuer-news-raw:v1:'+ROSTER_URL
CACHE_ONLY_FIELDS=('cache_source','source_payload_sha256','source_payload_bytes','cache_verified_at_epoch','cache_fresh_until_epoch')
def _cached_native_master(raw,c):
    """Recheck the actual existing 30-minute raw cache, never renew it."""
    from cache_store import get_cache_json
    row=get_cache_json('shared_provider:v1:'+sha256(NATIVE_MASTER_CACHE.encode()).hexdigest());now=time.time()
    if (not isinstance(row,dict)or row.get('error_kind')or c.get('cache_hit')is not True or c.get('http_request_sent')is not False
            or c.get('stale')not in(None,False)or c.get('http_status')is not None or c.get('http_status_observed')not in(None,False)
            or c.get('evidence_kind')is not None or any(k in c for k in CACHE_ONLY_FIELDS)):
        raise FilingError('Syntec native raw cache metadata invalid')
    stamp,until=row.get('fetched_at_epoch'),row.get('fresh_until_epoch');v=row.get('value')
    if (type(stamp)not in(int,float)or type(until)not in(int,float)or not math.isfinite(stamp)or not math.isfinite(until)
            or c.get('fetched_at_epoch')!=stamp or not 0<=now-stamp<=1800 or not now<until or not 0<until-stamp<=1801
            or not isinstance(v,dict)or v.get('url')!=ROSTER_URL or v.get('sha256')!=sha256(raw).hexdigest()
            or not isinstance(v.get('body_b64'),str)or len(v['body_b64'])>(2_500_000+2)//3*4):
        raise FilingError('Syntec native raw cache original time or payload invalid')
    try:decoded=base64.b64decode(v['body_b64'],validate=True)
    except(ValueError,UnicodeError):raise FilingError('Syntec native raw cache encoding invalid')from None
    if not 0<len(raw)<=2_500_000 or decoded!=raw:raise FilingError('Syntec native raw cache complete bytes mismatch')
    return {'cache_hit':True,'stale':False,'http_request_sent':False,'http_status':None,'http_status_observed':False,
            'evidence_kind':CACHED_NATIVE_MASTER_KIND,'cache_source':NATIVE_MASTER_CACHE,'source_payload_sha256':sha256(raw).hexdigest(),
            'source_payload_bytes':len(raw),'cache_verified_at_epoch':now,'cache_fresh_until_epoch':until}
def doc_contract(url,request=None):
    if url==CATALOG and request is None:return 150000,{'text/html','application/xhtml+xml'}
    if url==FORM and request==FORM_BODY:return 150000,{'text/html','application/xhtml+xml'}
    if PDF.fullmatch(str(url))and request is None:return 4_000_000,{'application/pdf'}
    raise FilingError('Syntec audited bridge transport route invalid')
def parse_catalog(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=150000:raise FilingError('Syntec catalog size invalid')
    s=BeautifulSoup(raw.decode('cp950',errors='strict'),'html.parser')
    links=s.find_all('a',href=f'javascript:readfile2("A","7750","{NAME}");')
    forms=s.find_all('form',action='/server-java/t57sb01',method='post')
    if len(links)!=1 or not forms:raise FilingError('Syntec catalog publication not unique')
    tr=links[0].find_parent('tr');cells=tr.find_all('td',recursive=False)if tr else[]
    text=[re.sub(r'\s+',' ',c.get_text(' ',strip=True)).strip()for c in cells]
    if (len(text)!=11 or text[:7]!=['7750','111 年 第四季','財務報告書','','','IFRSs合併財報','']or text[7]!=NAME or text[10]!=''
            or not re.fullmatch(r'[1-9]\d{0,2}(?:,\d{3})*',text[8])or not re.fullmatch(r'\d{3}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',text[9])):
        raise FilingError('Syntec catalog issuer consolidated year or metadata invalid')
    size=int(text[8].replace(',',''))
    if not 0<size<=4_000_000:raise FilingError('Syntec catalog declared PDF size invalid')
    date_part,clock_part=text[9].split();roc,month,day=map(int,date_part.split('/'));h,m,sec=map(int,clock_part.split(':'))
    published=datetime(roc+1911,month,day,h,m,sec,tzinfo=ZoneInfo('Asia/Taipei'))
    if published.timestamp()>time.time()or published.date()<datetime(2024,3,18).date():raise FilingError('Syntec catalog publication time invalid')
    field_sets=[{n.get('name')for n in f.select('input[name]')}for f in forms]
    if not any(set(FORM_BODY)<=keys for keys in field_sets):raise FilingError('Syntec published download form fields invalid')
    return {'issuer':'7750','filing_year':2022,'season':'4','scope':'consolidated','filename':NAME,'declared_bytes':size,'published_at':published.isoformat()}
def parse_download(raw,receipt):
    if not isinstance(raw,bytes)or not 0<len(raw)<=150000:raise FilingError('Syntec download form size invalid')
    s=BeautifulSoup(raw.decode('cp950',errors='strict'),'html.parser');links=s.select('a[href]')
    if len(links)!=1 or NAME not in s.get_text(' ',strip=True):raise FilingError('Syntec download form identity invalid')
    url=urljoin(FORM,links[0]['href']);match=PDF.fullmatch(url)
    if not match:raise FilingError('Syntec published temporary PDF route invalid')
    stamp=datetime.strptime(match[1]+match[2],'%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    epoch=receipt.get('retrieved_at')if isinstance(receipt,dict)else None
    # The portal names its temporary file with a whole-second server clock;
    # the real response can arrive <1 second before that path stamp locally.
    # Keep both original clocks, never reuse this stamp as publication/freshness.
    if type(epoch)not in(int,float)or not -1<=epoch-stamp<=300:raise FilingError('Syntec temporary PDF time unverified')
    return url
class BridgeHttp(PublicMopsHttp):
    def __init__(self,**kwargs):
        super().__init__(**kwargs);self.master=IssuerNewsHttp(self.deadline)
    def request(self,url,*,request=None,json_body=None):
        if url==ROSTER_URL:
            if request is not None or json_body is not None:raise FilingError('Syntec roster route invalid')
            raw=self.master.get(url);c=self.master.components[-1];self.components.append(dict(c))
            cached=c.get('evidence_kind')==CACHED_MASTER_KIND
            if cached:
                if (c.get('http_status')is not None or c.get('http_status_observed')is not False or c.get('http_request_sent')is not False
                        or c.get('cache_hit')is not True or c.get('stale')is not False or c.get('cache_source')!='official-company-roster:v2:.TW'
                        or c.get('source_url')!=url or c.get('source_payload_sha256')!=sha256(raw).hexdigest()or c.get('source_payload_bytes')!=len(raw)):
                    raise FilingError('Syntec cached roster metadata invalid')
                p=archive_response(raw,source_url=url,retrieved_at=c['fetched_at_epoch'],http_status=None,evidence_kind=CACHED_MASTER_KIND)
                p.update({k:c[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            elif c.get('cache_hit')is True and c.get('http_request_sent')is False and c.get('evidence_kind')is None:
                metadata=_cached_native_master(raw,c);self.components[-1].update(metadata)
                p=archive_response(raw,source_url=url,retrieved_at=c['fetched_at_epoch'],http_status=None,evidence_kind=CACHED_NATIVE_MASTER_KIND)
                p.update({k:metadata[k]for k in ('http_status_observed',*CACHE_ONLY_FIELDS)})
            else:
                if (c.get('http_request_sent')is not True or c.get('cache_hit')not in(None,False)
                        or c.get('stale')not in(None,False)or c.get('http_status')not in(None,200)
                        or 'http_status_observed'in c and c['http_status_observed']is not True
                        or c.get('evidence_kind')not in(None,'raw_http_response_bytes')or any(k in c for k in CACHE_ONLY_FIELDS)):
                    raise FilingError('Syntec native roster metadata contradicts observed HTTP')
                p=archive_response(raw,source_url=url,retrieved_at=c['fetched_at_epoch'],http_status=200)
            if read_response(p)!=raw:raise FilingError('Syntec roster archive invalid')
            return raw,p
        if url in{INDEX_URL}|{api_url(s)for s in STATEMENTS}|{template_url(s)for s in STATEMENTS}:
            return super().request(url,request=request,json_body=json_body)
        if json_body is not None:raise FilingError('Syntec document JSON request invalid')
        limit,types=doc_contract(url,request);diag={'url':url,'request_method':'POST'if request else'GET','http_request_sent':False};self.components.append(diag)
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise FilingError('network is disabled for tests')
        if proxy_url_for_request(url,PROVIDER)or any(os.getenv(k)for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        host=urlsplit(url).hostname;key=scope_key(PROVIDER,endpoint=host)
        if any(cooldown_state(scope_key(p,endpoint=host))for p in(PROVIDER,'Verified issuer news','TWSE MOPS public annual JSON')):raise SourceResponseError('cooldown')
        remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:raise SourceResponseError('timeout')
        args=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
              '--max-filesize',str(limit),'--proto','=https','--max-redirs','0','--retry','0','--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}']
        if request:
            for k,v in request.items():args+=['--data-urlencode',k+'='+v]
        args.append(url);parts,rc,error=collect_capped_process(args,min(self.deadline,time.monotonic()+remaining),body_limit=limit,headers=True)
        diag['http_request_sent']=bool(parts.get('process_started'));status,headers=_headers(parts['headers']);diag['http_status']=status
        try:meta=json.loads(parts['metadata'])
        except(ValueError,UnicodeError):meta={}
        response=httpx.Response(status,headers=headers,request=httpx.Request(diag['request_method'],url))if status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diag['error_kind']=kind;e=SourceResponseError(kind,status_code=status)
            if response is not None:e.response=response
            if status in(401,403,429)or status and status>=500:remember_failure(key,e)
            raise e
        if status is not None and status!=200:fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
        if rc or error:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
        if status!=200 or not isinstance(meta,dict)or meta.get('http_code')!=200 or meta.get('url_effective')!=url or meta.get('num_redirects')!=0:fail('transport_metadata_invalid')
        if headers.get('content-encoding','identity').lower()not in('','identity'):fail('unsupported_content_encoding')
        if headers.get('content-type','').split(';')[0].strip().lower()not in types:fail('unexpected_content_type')
        raw=parts['body']
        if not 0<len(raw)<=limit or time.monotonic()>=self.deadline:fail('timeout'if time.monotonic()>=self.deadline else'response_too_large')
        proof=archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=200)
        if read_response(proof)!=raw:raise FilingError('Syntec document complete original archive invalid')
        diag.update(status='complete',response_sha256=sha256(raw).hexdigest(),response_bytes=len(raw),fetched_at_epoch=proof['retrieved_at'])
        return raw,proof
