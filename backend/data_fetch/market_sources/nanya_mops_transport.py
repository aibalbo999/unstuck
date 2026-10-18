"""Only published Nanya English originals, using ordinary bounded MOPS GETs."""
from datetime import date
import re
import time
from . import uk_conference_transport as base
from search_provider_runtime import SourceResponseError

PROVIDER='MOPS Nanya prepared presentation'
PROXY_ENV=base.PROXY_ENV
_version=base._version
_headers=base._headers
collect_capped_process=base.collect_capped_process
observe_http_response=base.observe_http_response


def presentation_url(url):
    if not isinstance(url,str):return False
    match=re.fullmatch(r'https://mopsov\.twse\.com\.tw/nas/STR/2408([0-9]{4})([0-9]{2})([0-9]{2})E[0-9]{3}\.pdf',url)
    if not match:return False
    try:date(*map(int,match.groups()));return True
    except ValueError:return False


def download(url,*,deadline,diagnostics):
    # Reuse the proven capped transport body without widening the Universal
    # route contract, provider configuration, or its URL validation.
    if not presentation_url(url):raise SourceResponseError('transport_url_invalid')
    import os,json,httpx
    from hashlib import sha256
    from external_http_client import proxy_url_for_request
    diagnostics.update(http_request_sent=False,source_url=url,transport_client='native_curl',transport_request_profile='curl_default')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
    if proxy_url_for_request(url,PROVIDER) or any(os.getenv(k)for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
    diagnostics['transport_client_version']=_version(deadline)
    end=min(deadline,time.monotonic()+5.);remaining=end-time.monotonic()
    if remaining<=0:raise SourceResponseError('timeout')
    limit=8*1024*1024
    argv=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
          '--max-filesize',str(limit),'--proto','=https','--max-redirs','0','--retry','0',
          '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',url]
    parts,rc,failure=collect_capped_process(argv,end,body_limit=limit,headers=True)
    status,headers=_headers(parts['headers'])
    try:meta=json.loads(parts['metadata'])
    except (ValueError,UnicodeError):meta={}
    meta=meta if isinstance(meta,dict)else{}
    if status is None and type(meta.get('http_code'))is int and 200<=meta['http_code']<=599:status=meta['http_code']
    if time.monotonic()>=end:failure='timeout'
    raw=parts['body'];complete=not rc and failure is None
    diagnostics.update(http_request_sent=parts['process_started'],http_status=status,response_bytes=len(raw),response_complete=complete,
                       response_hash_scope='full_received_body'if complete else'captured_prefix',transport_returncode=rc)
    diagnostics['response_sha256'if complete else'captured_prefix_sha256']=sha256(raw).hexdigest()
    response=httpx.Response(status,headers=headers,request=httpx.Request('GET',url))if status else None
    observe_http_response(response)
    def refuse(kind):
        exc=SourceResponseError(kind,status_code=status);exc.response=response;exc.diagnostic.update(diagnostics);raise exc
    if status is not None and status!=200:refuse({401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
    if failure or rc:refuse(failure or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
    if status!=200 or meta.get('http_code')!=200 or meta.get('url_effective')!=url or meta.get('num_redirects')!=0:refuse('transport_metadata_invalid')
    if headers.get('content-encoding','identity').lower()not in ('','identity'):refuse('unsupported_content_encoding')
    if headers.get('content-type','').split(';')[0].strip().lower()!='application/pdf' or not raw.startswith(b'%PDF-'):refuse('unexpected_content_type')
    return raw
