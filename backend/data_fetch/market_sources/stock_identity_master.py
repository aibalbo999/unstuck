"""Bounded whole-market identities with shared, original-byte cache provenance.

A master is an identity prerequisite. It is never a peer valuation observation,
never changes the rows' publication dates, and never proves business similarity.
"""
from __future__ import annotations
from hashlib import sha256
import json,math,os,time
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError,cooldown_state,scope_key,remember_failure,observe_http_response
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers

URL='https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo'
CACHE_KEY='finmind-stock-identity-master:v1'
PROVIDER='FinMind TaiwanStockInfo identity master'
FRESH_SECONDS=86400
ERROR_RETRY_SECONDS=600
MAX_BYTES=2500000
TOTAL_SECONDS=12
PROXY_ENV=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')

class MasterRows(list):
    def __init__(self,rows,metadata):
        super().__init__(rows)
        self.identity_master_metadata=metadata


def _pairs(items):
    value={}
    for key,item in items:
        if key in value:raise ValueError('duplicate identity-master field')
        value[key]=item
    return value


def parse_master(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES:
        raise ValueError('identity master size invalid')
    payload=json.loads(raw,object_pairs_hook=_pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite master JSON')))
    if not isinstance(payload,dict)or type(payload.get('status'))is not int or payload['status']!=200:
        raise ValueError('identity master provider response rejected')
    data=payload.get('data')
    if not isinstance(data,list)or not 800<=len(data)<=30000:
        raise ValueError('identity master full snapshot unavailable')
    records=[]
    for row in data:
        if not isinstance(row,dict):raise ValueError('identity master row invalid')
        # Preserve the legacy loader's five source fields exactly. The existing
        # per-target dated/master/market/category gate remains the authority.
        stock_id=str(row.get('stock_id','')).strip()
        stock_name=str(row.get('stock_name','')).strip()
        if stock_id and stock_name:
            records.append({'stock_id':stock_id,'stock_name':stock_name,
                'industry_category':str(row.get('industry_category','')).strip(),
                'type':str(row.get('type','')).strip(),'date':str(row.get('date','')).strip()})
    if not records:raise ValueError('identity master empty')
    return records


def _download():
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
    if proxy_url_for_request(URL,PROVIDER)or any(os.getenv(k)for k in PROXY_ENV):
        raise SourceResponseError('proxy_configuration_unsupported')
    key=scope_key(PROVIDER,endpoint='api.finmindtrade.com')
    if cooldown_state(key):raise SourceResponseError('cooldown')
    argv=['/usr/bin/curl','--disable','--silent','--max-time',str(TOTAL_SECONDS),
        '--connect-timeout','3','--max-filesize',str(MAX_BYTES),'--proto','=https',
        '--max-redirs','0','--retry','0','-H','Accept: application/json',
        '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',URL]
    parts,rc,error=collect_capped_process(argv,time.monotonic()+TOTAL_SECONDS,body_limit=MAX_BYTES,headers=True)
    return _consume_download(parts,rc,error)


def _consume_download(parts,rc,error):
    key=scope_key(PROVIDER,endpoint='api.finmindtrade.com')
    status,headers=_headers(parts['headers'])
    try:meta=json.loads(parts['metadata'],object_pairs_hook=_pairs)
    except (ValueError,UnicodeError):meta={}
    meta=meta if isinstance(meta,dict)else{}
    if status is None and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599:status=meta['http_code']
    response=httpx.Response(status,headers=headers,request=httpx.Request('GET',URL))if status else None
    if response is not None:observe_http_response(response)
    observed = (parts.get('process_started') is True and type(meta.get('http_code')) is int
                and 200<=meta['http_code']<=599 and meta.get('url_effective')==URL
                and type(meta.get('ssl_verify_result'))is int and meta['ssl_verify_result']==0
                and type(meta.get('proxy_used'))is int and meta['proxy_used']==0)
    diagnostic={'http_request_sent':True if observed else None,
                'http_request_count':int(observed),'http_status':status,
                'client_process_started':bool(parts.get('process_started'))}
    def fail(kind):
        exc=SourceResponseError(kind,status_code=status)
        exc.master_diagnostic={**diagnostic,'error_kind':kind}
        if response is not None:exc.response=response
        if status in {401,402,403,429}or status and status>=500:remember_failure(key,exc)
        raise exc
    if status is not None and status!=200:
        fail({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
    if error or rc:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
    if (status!=200 or meta.get('http_code')!=status or meta.get('url_effective')!=URL
            or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0
            or type(meta.get('ssl_verify_result'))is not int or meta['ssl_verify_result']!=0
            or type(meta.get('proxy_used'))is not int or meta['proxy_used']!=0
            or parts.get('process_started')is not True):
        fail('transport_metadata_invalid')
    if headers.get('content-encoding','identity').lower()not in {'','identity'}:fail('unsupported_content_encoding')
    if headers.get('content-type','').split(';')[0].strip().lower()not in {'application/json','text/json'}:fail('unexpected_content_type')
    raw=parts['body']
    if not 0<len(raw)<=MAX_BYTES or type(meta.get('size_download'))not in (int,float)or not math.isfinite(meta['size_download'])or meta['size_download']!=len(raw):
        fail('transport_body_incomplete')
    proof=archive_response(raw,source_url=URL,retrieved_at=time.time(),http_status=status)
    try:parse_master(raw)
    except ValueError as original:
        # Preserve an explicit semantic refusal, even when the HTTP leg was200.
        try:provider_status=json.loads(raw).get('status')
        except (ValueError,UnicodeError,AttributeError):provider_status=None
        if type(provider_status)is int and provider_status in {401,402,403,429}:
            kind={401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}[provider_status]
            semantic=SourceResponseError(kind);semantic.response=httpx.Response(provider_status,request=httpx.Request('GET',URL))
            remember_failure(key,semantic)
        exc=SourceResponseError('provider_response_rejected',status_code=status)
        exc.master_diagnostic={**diagnostic,'provider_status':provider_status,'raw_receipt':proof,'error_kind':'provider_response_rejected'}
        raise exc from original
    return {'schema':'finmind-stock-identity-master.v1','raw_receipt':proof,
            'transport_summary':{**diagnostic,'response_sha256':sha256(raw).hexdigest()}}


def read_master():
    attempt={}
    def acquire():
        try:
            value=_download()
            attempt.update(value.get('transport_summary') or {})
            return value
        except Exception as exc:
            attempt.update(getattr(exc,'master_diagnostic',{}) or {})
            raise
    payload,meta=shared_fetch(CACHE_KEY,acquire,freshness_seconds=FRESH_SECONDS,
        retention_seconds=FRESH_SECONDS,error_retry_seconds=ERROR_RETRY_SECONDS,
        use_cache=True,lock_wait_seconds=15)
    info={**meta,'provider':PROVIDER,'source_url':URL,'evidence_scope':'identity_master_not_peer_metrics',
          'http_request_count':0,'http_request_sent':False,**attempt}
    if meta.get('error_kind')or meta.get('stale')or not isinstance(payload,dict):
        return [],info
    try:
        if payload.get('schema')!='finmind-stock-identity-master.v1':raise ValueError('schema invalid')
        proof=payload.get('raw_receipt')
        if (not isinstance(proof,dict)or proof.get('source_url')!=URL or proof.get('http_status')!=200
                or proof.get('evidence_kind')!='raw_http_response_bytes'):raise ValueError('receipt invalid')
        raw=read_response(proof)
        rows=parse_master(raw)
    except Exception:
        return [],{**info,'error_kind':'cached_master_integrity_invalid'}
    # A cache read retains the old proof; it is not a fresh HTTP sample.
    info.update(raw_receipt=proof,source_payload_sha256=sha256(raw).hexdigest())
    if meta.get('cache_hit') is True:
        info.update(http_request_count=0,http_request_sent=False)
    return rows,info
