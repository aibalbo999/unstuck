"""Capped original-byte transport for one qualified peer-income protocol.

All cache keys describe the request's semantic identity. A publisher-style
cache-buster never changes local ownership or permits bypassing a saved guard.
"""
from contextlib import suppress
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json,math,os,re,sqlite3,time
from urllib.parse import urlencode,urlsplit,parse_qs

import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError,cooldown_state,scope_key,observe_http_response,remember_failure
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers
from .mops_public_annual import _security_refusal_page
from .peer_reference_income import COMPANY,CODE,quarter_end

PROVIDER='TWSE official peer reference income'
HOME='https://mopsfin.twse.com.tw/'
REPORT=HOME+'compare/report'
REFERENCE='https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d'
METHODOLOGY='https://www.twse.com.tw/zh/trading/historical/bwibbu-day.html'
INDEX='https://doc.twse.com.tw/server-java/t57sb01'
TTL=1800
RAW_PREFIX='peer-reference-income-raw:v1:'
SCHEMA='peer-reference-native-http.v1'
ARCHIVE_FIELDS={'status','source_url','retrieved_at','http_status','raw_response_sha256',
    'raw_response_path','raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed'}


def spec(kind,*,day=None,year=None,quarter=None):
    params={};data=None;method='GET';mime='text/html';encoding='utf-8';limit=250000
    if kind=='home':url=HOME
    elif kind=='methodology':url=METHODOLOGY
    elif kind=='reference':
        if type(day)is not date:raise ValueError('reference day required')
        params={'day':day.isoformat()};url=REFERENCE+'?'+urlencode({'date':day.strftime('%Y%m%d'),'selectType':'ALL','response':'json'})
        mime='application/json';limit=1000000
    elif kind=='index':
        quarter_end(year,4);params={'year':year};encoding='big5'
        url=INDEX+'?'+urlencode({'co_id':CODE,'colorchg':'1','mtype':'A','step':'1','year':str(year-1911)})
    elif kind=='income':
        quarter_end(year,quarter);params={'year':year,'quarter':quarter};url=REPORT;method='POST'
        data={'compareItem':'IncomeStatement','quarter':'true','ylabel':'','ys':f'{year}{quarter}',
            'revenue':'true','bcodeAvg':'false','companyAvg':'false','qnumber':'','companyId':COMPANY}
    else:raise ValueError('unsupported reference-income request')
    return {'kind':kind,'params':params,'url':url,'method':method,'data':data,'mime':mime,'encoding':encoding,'limit':limit}


def canonical_spec(value):
    if not isinstance(value,dict):raise ValueError('invalid request specification')
    p=value.get('params')or{}
    if not isinstance(p,dict):raise ValueError('invalid request parameters')
    expected=spec(value.get('kind'),day=date.fromisoformat(p['day'])if'day'in p else None,
        year=p.get('year'),quarter=p.get('quarter'))
    if value!=expected:raise ValueError('request specification not admitted')
    return expected


def raw_key(request):
    return RAW_PREFIX+json.dumps(canonical_spec(request),sort_keys=True,ensure_ascii=True,separators=(',',':'))


def _url_matches(actual,request):
    if request['kind']!='reference':return actual==request['url']
    if not isinstance(actual,str):return False
    p=urlsplit(actual);base=urlsplit(request['url']);q=parse_qs(p.query,keep_blank_values=True)
    if '_'in q:
        nonce=q.pop('_')
        if len(nonce)!=1 or not re.fullmatch(r'[0-9]{13}',nonce[0]):return False
    return (p.scheme,p.netloc,p.path,p.fragment)==(base.scheme,base.netloc,base.path,'')and q==parse_qs(base.query)


def _manifest(packet):
    return json.dumps({k:v for k,v in packet.items()if k!='metadata_manifest'},sort_keys=True,
        ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()


def _archive(proof,url,stamp,kind,status,limit):
    if (not isinstance(proof,dict)or set(proof)!=ARCHIVE_FIELDS or proof.get('status')!='archived'
            or proof.get('source_url')!=url or proof.get('retrieved_at')!=stamp
            or proof.get('http_status')!=status or type(proof.get('http_status'))is not type(status)
            or proof.get('evidence_kind')!=kind or proof.get('historical_point_in_time_verified')is not False
            or proof.get('finality_guaranteed')is not False):raise ValueError('original metadata mismatch')
    raw=read_response(proof,max_bytes=limit)
    if not 0<len(raw)<=limit or len(raw)!=proof.get('raw_response_bytes')or sha256(raw).hexdigest()!=proof.get('raw_response_sha256'):
        raise ValueError('original full body mismatch')
    return raw


def _error(kind,*,status=None,observed=False):
    exc=SourceResponseError(kind,status_code=status)
    exc.diagnostic.update(http_status_observed=observed,response_complete=False)
    return exc


def receipt_body(packet,request,*,now=None,check_owner=True):
    request=canonical_spec(request);now=time.time()if now is None else now
    if (not isinstance(packet,dict)or set(packet)!={'schema','spec','request_url','native','fetched_at_epoch','raw_receipt','metadata_manifest'}
            or packet.get('schema')!=SCHEMA or packet.get('spec')!=request or not _url_matches(packet.get('request_url'),request)):
        raise ValueError('unverified native request identity')
    stamp=packet['fetched_at_epoch'];url=packet['request_url']
    if type(stamp)not in(int,float)or not math.isfinite(stamp)or not 0<=now-stamp<TTL:
        raise ValueError('native response expired')
    raw=_archive(packet['raw_receipt'],url,stamp,'raw_http_response_bytes',200,request['limit'])
    expected={'http_status':200,'http_status_observed':True,'response_complete':True,'http_request_sent':True,
        'return_code':0,'num_redirects':0,'proxy_used':0,'ssl_verify_result':0,'response_bytes':len(raw)}
    if packet['native']!=expected or any(type(packet['native'][k])is not type(v)for k,v in expected.items()):
        raise ValueError('native complete transport not established')
    if _archive(packet['metadata_manifest'],url,stamp,'private_acquisition_manifest',None,32768)!=_manifest(packet):
        raise ValueError('request/body manifest mismatch')
    if check_owner:
        from cache_store import peek_cache_json
        owner=peek_cache_json('shared_provider:v1:'+sha256(raw_key(request).encode()).hexdigest())
        fetched=owner.get('fetched_at_epoch')if isinstance(owner,dict)else None
        until=owner.get('fresh_until_epoch')if isinstance(owner,dict)else None
        if (not isinstance(owner,dict)or owner.get('value')!=packet or owner.get('error_kind')
                or type(fetched)not in(int,float)or not math.isfinite(fetched)or not 0<=fetched-stamp<=10
                or type(until)not in(int,float)or not math.isfinite(until)or not now<until<=stamp+TTL+10):
            raise ValueError('independent raw owner missing or expired')
    return raw


class PeerIncomeHttp:
    def __init__(self,*,seconds=20):
        self.deadline=time.monotonic()+seconds;self.components=[];self.http_request_count=0

    def _emit(self,diag,packet=None):
        from .ncc_mobile_peer_transport import peer_receipt_observation_enabled
        if not peer_receipt_observation_enabled()or not diag.get('client_process_started'):return
        from provider_correlation import current_correlation,current_source_identity
        from provider_sla import record_source_audit_entries
        context=current_correlation()
        if not(context.get('ticker')and context.get('fetch_id')and context.get('operation_id')
                and current_source_identity()==('dynamic_peer_metrics','FinMind/yfinance')):return
        component=deepcopy(diag)
        if packet is not None:
            component['original_receipt']={**packet['raw_receipt'],'http_status_observed':True,
                'response_complete':True,'request_method':packet['spec']['method'],'cache_hit':False}
        with suppress(sqlite3.Error):record_source_audit_entries([{**context,'source':'dynamic_peer_metrics',
            'provider':PROVIDER+' native HTTP','peer_ticker':'6230.TW','record_count':0,
            'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
            'status':'success'if packet else'error','http_request_sent':diag.get('http_request_sent'),
            'http_status':diag.get('http_status'),'http_status_observed':diag.get('http_status_observed'),
            'response_complete':bool(packet),'response_bytes':diag.get('response_bytes'),
            'response_sha256':diag.get('response_sha256'),'component_statuses':[component],
            'message':'Reference-income transport only; no P/E value, financial comparison or acquisition success counted.'}])

    def _consume(self,request,url,parts,rc,error,diag):
        status,headers=_headers(parts['headers'])
        try:meta=json.loads(parts['metadata'])
        except(ValueError,UnicodeError):meta={}
        if not isinstance(meta,dict):meta={}
        if status is None and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599:status=meta['http_code']
        raw=parts['body'];started=parts.get('process_started')is True
        known=(started and type(status)is int and status==meta.get('http_code')and 200<=status<=599
            and meta.get('url_effective')==url and meta.get('ssl_verify_result')==0 and type(meta.get('ssl_verify_result'))is int
            and meta.get('proxy_used')==0 and type(meta.get('proxy_used'))is int)
        diag.update(client_process_started=started,http_request_sent=True if known else None if started else False,
            http_status=status,http_status_observed=status is not None,response_complete=False,
            response_bytes=len(raw),response_sha256=sha256(raw).hexdigest(),request_method=request['method'])
        self.http_request_count+=int(known)
        response=httpx.Response(status,headers=headers,request=httpx.Request(request['method'],url))if status else None
        if response is not None:observe_http_response(response)
        def fail(kind):
            diag['error_kind']=kind;self._emit(diag)
            exc=SourceResponseError(kind,status_code=status)
            exc.diagnostic.update(http_status_observed=status is not None,response_complete=False,
                response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
            if response is not None:exc.response=response
            if kind=='access_denied'or status in{401,402,403,429}or status and status>=500:
                for provider in self._guard_providers(request):remember_failure(scope_key(provider,endpoint=urlsplit(url).hostname),exc)
            if status==429:
                from provider_throttle import mark_rate_limit_cooldown
                mark_rate_limit_cooldown(self._admission_provider(request),exc)
            raise exc
        if status is not None and status!=200:fail({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
        if error or rc:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
        if not known or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0:fail('transport_metadata_invalid')
        if _security_refusal_page(raw):fail('access_denied')
        mime=headers.get('content-type','').lower().split(';')
        if mime[0].strip()!=request['mime']or headers.get('content-encoding','identity').lower()not in{'','identity'}:fail('unexpected_content_type')
        if request['mime']=='text/html'and not any(s.strip().replace(' ','').replace('-','')=='charset='+request['encoding'].replace('-','')for s in mime[1:]):fail('unexpected_encoding')
        if not 0<len(raw)<=request['limit']or type(meta.get('size_download'))not in(int,float)or meta['size_download']!=len(raw):fail('transport_body_incomplete')
        if time.monotonic()>=self.deadline:fail('timeout')
        stamp=time.time();packet={'schema':SCHEMA,'spec':deepcopy(request),'request_url':url,'fetched_at_epoch':stamp,
            'native':{'http_status':200,'http_status_observed':True,'response_complete':True,'http_request_sent':True,
                'return_code':0,'num_redirects':0,'proxy_used':0,'ssl_verify_result':0,'response_bytes':len(raw)},
            'raw_receipt':archive_response(raw,source_url=url,retrieved_at=stamp,http_status=200,max_bytes=request['limit'])}
        packet['metadata_manifest']=archive_response(_manifest(packet),source_url=url,retrieved_at=stamp,http_status=None,
            evidence_kind='private_acquisition_manifest',max_bytes=32768)
        receipt_body(packet,request,check_owner=False);diag['response_complete']=True;self._emit(diag,packet)
        return packet

    @staticmethod
    def _admission_provider(request):
        return 'TWSE/TPEx official peer valuation OpenAPI'if request['kind']in{'reference','methodology'}else'TWSE MOPS official financial comparison'

    def _guard_providers(self,request):
        return (PROVIDER,self._admission_provider(request),'Verified issuer news')

    def _download(self,request,diag):
        def block(kind):
            diag.update(error_kind=kind,http_request_sent=False,http_status=None,http_status_observed=False,response_complete=False)
            exc=SourceResponseError(kind);exc.diagnostic.update(http_status_observed=False,response_complete=False);raise exc
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':block('test_network_disabled')
        if proxy_url_for_request(request['url'],PROVIDER)or any(os.getenv(k)for k in('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')):block('proxy_configuration_unsupported')
        host=urlsplit(request['url']).hostname
        if any(cooldown_state(scope_key(p,endpoint=host))for p in self._guard_providers(request)):block('cooldown')
        # A new consumer must not bypass a live original or failure saved by
        # the existing anonymous raw transport for this exact endpoint.
        from cache_store import peek_cache_json
        old=peek_cache_json('shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+request['url']).encode()).hexdigest())
        if isinstance(old,dict)and any(type(old.get(k))in(int,float)and math.isfinite(old[k])and old[k]>time.time()
                for k in ('fresh_until_epoch','retry_after_epoch')):block('legacy_raw_cache_still_live')
        from provider_resilience import _check_provider_state,ProviderCircuitOpenError
        from provider_throttle import provider_throttle_state,enforce_provider_throttle,ProviderRateLimitOpenError
        provider=self._admission_provider(request);remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:block('timeout')
        throttle=provider_throttle_state(provider)
        if throttle.get('open'):block('cooldown')
        if float(throttle.get('min_interval_seconds')or 0)>remaining:block('request_pacing')
        wait=float(throttle.get('last_call_at')or 0)+float(throttle.get('min_interval_seconds')or 0)-time.time()
        if wait>remaining:block('request_pacing')
        try:_check_provider_state(provider);enforce_provider_throttle(provider)
        except(ProviderCircuitOpenError,ProviderRateLimitOpenError):block('cooldown')
        remaining=min(5.,self.deadline-time.monotonic())
        if remaining<=0:block('timeout')
        url=request['url']
        if request['kind']=='reference':url+='&_='+str(int(time.time()*1000))
        argv=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
            '--max-filesize',str(request['limit']),'--proto','=https','--max-redirs','0','--retry','0',
            '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}']
        if request['method']=='POST':argv+=['--request','POST','--header','Content-Type: application/x-www-form-urlencoded; charset=UTF-8','--data-raw',urlencode(request['data'])]
        argv.append(url)
        parts,rc,error=collect_capped_process(argv,min(self.deadline,time.monotonic()+remaining),body_limit=request['limit'],headers=True)
        return self._consume(request,url,parts,rc,error,diag)

    def get(self,request):
        request=canonical_spec(request);diag={'url':request['url'],'http_request_sent':False,'http_status_observed':False,'response_complete':False}
        self.components.append(diag)
        if time.monotonic()>=self.deadline:raise _error('timeout')
        value,meta=shared_fetch(raw_key(request),lambda:self._download(request,diag),freshness_seconds=TTL,
            retention_seconds=TTL,error_retry_seconds=120,lock_wait_seconds=min(1.,max(0.,self.deadline-time.monotonic())))
        diag.update(cache_hit=bool(meta.get('cache_hit')),fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind')or meta.get('stale')or not isinstance(value,dict):
            raise _error(diag.get('error_kind')or meta.get('error_kind')or'original_unavailable',
                status=diag.get('http_status'),observed=diag.get('http_status_observed')is True)
        raw=receipt_body(value,request)
        if time.monotonic()>=self.deadline:raise _error('timeout')
        return raw,value
