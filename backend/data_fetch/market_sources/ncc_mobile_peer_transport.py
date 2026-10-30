"""One anonymous capped NCC read; cached originals never become new HTTP."""
import json,time,math,os,sqlite3
from hashlib import sha256
from contextlib import suppress,contextmanager
from contextvars import ContextVar
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response
from shared_provider_cache import shared_fetch
from search_provider_runtime import SourceResponseError,cooldown_state,scope_key,observe_http_response,remember_failure
from .construction_cohort_transport import _headers
from .ncc_mobile_peer_cohort import SOURCE_URL,PROVIDER,LIMIT,TTL,IDENTITIES,today,parse_members,_original
RAW_KEY='ncc-mobile-membership-raw:v1:'
_RECORD_RECEIPTS=ContextVar('ncc_membership_receipt_observation',default=False)


@contextmanager
def receipt_observation_scope(enabled):
 token=_RECORD_RECEIPTS.set(enabled is True)
 try:yield
 finally:_RECORD_RECEIPTS.reset(token)


class MobileHttp:
 def __init__(self,deadline):
  self.deadline=deadline;self.http_request_count=0;self.components=[]

 def _consume(self,parts,rc,error,diagnostic):
  status,headers=_headers(parts['headers'])
  try:meta=json.loads(parts['metadata'])
  except(ValueError,UnicodeError):meta={}
  if not isinstance(meta,dict):meta={}
  known=(parts.get('process_started')is True and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599
    and meta.get('url_effective')==SOURCE_URL and type(meta.get('ssl_verify_result'))is int and meta['ssl_verify_result']==0
    and type(meta.get('proxy_used'))is int and meta['proxy_used']==0)
  if status is None and known:status=meta['http_code']
  diagnostic.update(http_request_sent=True if known else None,http_request_count=int(known),http_status=status)
  self.http_request_count+=int(known)
  response=httpx.Response(status,headers=headers,request=httpx.Request('GET',SOURCE_URL))if status else None
  if response is not None:observe_http_response(response)
  if known and _RECORD_RECEIPTS.get():
   from provider_correlation import current_correlation,current_source_identity
   from provider_sla import record_source_audit_entries
   context=current_correlation()
   if (context.get('ticker')in IDENTITIES and context.get('fetch_id')and context.get('operation_id')
       and current_source_identity()==('dynamic_peer_metrics','FinMind/yfinance')):
    with suppress(sqlite3.Error):record_source_audit_entries([{**context,'source':'dynamic_peer_metrics',
     'provider':PROVIDER+' native HTTP','event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
     'record_count':0,'status':'success'if status==200 else'error','http_status':status,'http_request_sent':True,
     'response_sha256':sha256(parts['body']).hexdigest(),'response_bytes':len(parts['body']),
     'message':'Operator membership transport only; no peer financial metrics verified.'}])
  def fail(kind):
   diagnostic['error_kind']=kind;exc=SourceResponseError(kind,status_code=status)
   if response is not None:exc.response=response
   if status in{401,402,403,429}or status and status>=500:remember_failure(scope_key(PROVIDER,endpoint='api.ncc.gov.tw'),exc)
   raise exc
  if status is not None and status!=200:fail({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
  if rc or error:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
  if not known or status!=200 or meta.get('http_code')!=200 or type(meta.get('num_redirects'))is not int or meta['num_redirects']!=0:fail('transport_metadata_invalid')
  mime=headers.get('content-type','').split(';')[0].strip().lower()
  if mime not in{'','application/json','text/json','text/plain','application/octet-stream'}or headers.get('content-encoding','identity').lower()not in{'','identity'}:fail('unexpected_content_type')
  raw=parts['body'];size=meta.get('size_download')
  if not 0<len(raw)<=LIMIT or type(size)not in(int,float)or not math.isfinite(size)or size!=len(raw):fail('transport_body_incomplete')
  try:parse_members(raw,today=today())
  except(ValueError,UnicodeError,RecursionError):fail('ncc_original_invalid')
  if time.monotonic()>=self.deadline:fail('timeout')
  stamp=time.time();proof=archive_response(raw,source_url=SOURCE_URL,retrieved_at=stamp,http_status=200)
  if proof.get('status')!='archived':fail('original_archive_unavailable')
  proof.update(fresh_until_epoch=stamp+TTL,http_status_observed=True)
  return {'receipt':proof}

 def _download(self,diagnostic):
  if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
  if proxy_url_for_request(SOURCE_URL,PROVIDER)or any(os.getenv(k)for k in('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')):raise SourceResponseError('proxy_configuration_unsupported')
  if cooldown_state(scope_key(PROVIDER,endpoint='api.ncc.gov.tw')):raise SourceResponseError('cooldown')
  remaining=min(5.,self.deadline-time.monotonic())
  if remaining<=0:raise SourceResponseError('timeout')
  argv=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
   '--max-filesize',str(LIMIT),'--proto','=https','--max-redirs','0','--retry','0','--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',SOURCE_URL]
  parts,rc,error=collect_capped_process(argv,min(self.deadline,time.monotonic()+remaining),body_limit=LIMIT,headers=True)
  return self._consume(parts,rc,error,diagnostic)

 def get(self):
  diagnostic={'source_url':SOURCE_URL,'http_request_sent':False,'http_request_count':0};self.components.append(diagnostic)
  if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
  value,meta=shared_fetch(RAW_KEY+SOURCE_URL,lambda:self._download(diagnostic),freshness_seconds=TTL,retention_seconds=TTL,
    error_retry_seconds=120,lock_wait_seconds=min(1.,max(0.,self.deadline-time.monotonic())))
  diagnostic.update(cache_hit=bool(meta.get('cache_hit')),fetched_at_epoch=meta.get('fetched_at_epoch'))
  if meta.get('error_kind')or meta.get('stale')or not isinstance(value,dict):raise SourceResponseError(diagnostic.get('error_kind')or meta.get('error_kind')or'original_unavailable')
  proof=value.get('receipt');raw=_original(proof,SOURCE_URL)
  if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')
  return raw,proof
