"""One CAL IR route with bounded wire/decoded evidence; no body cache."""
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import json,math,os,re,time,zlib
import httpx
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .official_xbrl_financial import FilingError
from . import issuer_news_transport as native

URL='https://www.china-airlines.com/nz/en/about-china-airlines/investor-relations?tab=FinancialReportsTab'
POLICY='cal-ir-content-encoding-v1'
LIMIT=1_500_000
ARCHIVE_FIELDS={'status','source_url','retrieved_at','http_status','raw_response_sha256','raw_response_path','raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed'}
MARKERS={'transport_policy','cal_ir_metadata','decoded_original','cal_ir_manifest'}
RECEIPT_FIELDS=ARCHIVE_FIELDS|MARKERS|{'http_status_observed','request_method','response_complete','cache_hit'}
META_FIELDS={'http_status','url_effective','num_redirects','method','proxy_used','ssl_verify_result','content_type','content_encoding','content_length','size_download','wire_bytes','wire_sha256','decoded_bytes','decoded_sha256'}

def _bad(reason):raise FilingError('CAL IR original '+reason)
def _same(a,b):return json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False)==json.dumps(b,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def is_marked(receipt):return isinstance(receipt,dict)and bool(MARKERS&receipt.keys())
def _number(v):return type(v)in(int,float)and math.isfinite(v)

def decode_wire(wire,encoding):
    if not isinstance(wire,bytes)or not 0<len(wire)<=LIMIT:_bad('wire size invalid')
    if encoding in ('','identity'):return wire
    if encoding!='gzip':_bad('encoding unsupported')
    try:
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS);raw=decoder.decompress(wire,LIMIT+1)
        if not 0<len(raw)<=LIMIT or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:_bad('gzip incomplete, oversized, trailing or multiple members')
        return raw
    except zlib.error as exc:raise FilingError('CAL IR gzip CRC or framing invalid')from exc

def _headers(raw):
    if not isinstance(raw,bytes)or not raw.endswith(b'\r\n\r\n'):_bad('headers incomplete')
    blocks=[b for b in raw.decode('iso-8859-1').split('\r\n\r\n')if b.startswith('HTTP/')]
    if not blocks:_bad('headers missing')
    lines=blocks[-1].split('\r\n');match=re.fullmatch(r'HTTP/\S+ ([1-5]\d{2})(?: .*)?',lines[0])
    if not match:_bad('status header invalid')
    out={}
    for line in lines[1:]:
        key,sep,value=line.partition(':');key=key.lower()
        if sep and key in {'content-type','content-encoding','content-length','retry-after'}:
            if key in out:_bad('duplicate contract header')
            out[key]=value.strip()
    return int(match[1]),out

def _metadata_valid(meta,wire,raw):
    if not isinstance(meta,dict)or set(meta)!=META_FIELDS:return False
    return (type(meta['http_status'])is int and meta['http_status']==200 and meta['url_effective']==URL
            and meta['method']=='GET'and all(type(meta[k])is int and meta[k]==0 for k in ('num_redirects','proxy_used','ssl_verify_result'))
            and meta['content_type']in {'text/html','application/xhtml+xml'}and meta['content_encoding']in {'','identity','gzip'}
            and (meta['content_length']is None or type(meta['content_length'])is int and meta['content_length']==len(wire))
            and _number(meta['size_download'])and meta['size_download']==len(wire)
            and type(meta['wire_bytes'])is int and meta['wire_bytes']==len(wire)
            and type(meta['decoded_bytes'])is int and meta['decoded_bytes']==len(raw)
            and meta['wire_sha256']==sha256(wire).hexdigest()and meta['decoded_sha256']==sha256(raw).hexdigest())

def _archive_bytes(proof,stamp,kind,status,limit):
    if (not isinstance(proof,dict)or set(proof)!=ARCHIVE_FIELDS or proof.get('status')!='archived'
            or proof.get('source_url')!=URL or not _number(proof.get('retrieved_at'))or proof['retrieved_at']!=stamp
            or type(proof.get('http_status'))is not type(status)or proof['http_status']!=status
            or proof.get('evidence_kind')!=kind or type(proof.get('raw_response_bytes'))is not int
            or not 0<proof['raw_response_bytes']<=limit
            or proof.get('historical_point_in_time_verified')is not False or proof.get('finality_guaranteed')is not False):_bad('archive receipt invalid')
    raw=read_response(proof,max_bytes=limit)
    if len(raw)!=proof['raw_response_bytes']:_bad('archive size mismatch')
    return raw

def read_original(receipt):
    """Replay both originals and immutable acquisition binding, never current cache."""
    try:
        if (not isinstance(receipt,dict)or set(receipt)!=RECEIPT_FIELDS or receipt['transport_policy']!=POLICY
                or receipt['http_status_observed']is not True or receipt['response_complete']is not True
                or receipt['request_method']!='GET'or receipt['cache_hit']is not False):_bad('transport receipt invalid')
        stamp=receipt['retrieved_at']
        if not _number(stamp)or not datetime(2026,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()<=stamp<=time.time():_bad('original epoch invalid')
        wire=_archive_bytes({k:receipt[k]for k in ARCHIVE_FIELDS},stamp,'raw_http_response_bytes',200,LIMIT)
        raw=_archive_bytes(receipt['decoded_original'],stamp,'decoded_http_response_bytes',None,LIMIT)
        meta=receipt['cal_ir_metadata']
        if not _metadata_valid(meta,wire,raw)or decode_wire(wire,meta['content_encoding'])!=raw:_bad('wire/decoded binding invalid')
        manifest=_archive_bytes(receipt['cal_ir_manifest'],stamp,'private_acquisition_manifest',None,16384)
        expected={k:v for k,v in receipt.items()if k!='cal_ir_manifest'}
        if not _same(json.loads(manifest),expected):_bad('acquisition binding differs')
        return raw
    except (KeyError,TypeError,ValueError,OSError,EOFError,zlib.error,OverflowError,RecursionError)as exc:
        if isinstance(exc,FilingError):raise
        raise FilingError('CAL IR original replay failed closed')from exc

def request_original(http,diagnostic,validate_page):
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
    if native.proxy_url_for_request(URL,native.PROVIDER)or any(os.getenv(k)for k in native.PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
    key=native.scope_key(native.PROVIDER,endpoint='www.china-airlines.com')
    if native.cooldown_state(key):raise SourceResponseError('cooldown')
    remaining=min(5.,http.deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    stop=min(http.deadline,time.monotonic()+remaining)
    args=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
          '--max-filesize',str(LIMIT),'--proto','=https','--max-redirs','0','--retry','0','--header','Accept-Encoding: gzip',
          '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',URL]
    parts,rc,error=native.collect_capped_process(args,stop,body_limit=LIMIT,headers=True)
    diagnostic['http_request_sent']=bool(parts.get('process_started'));http.http_request_count+=int(diagnostic['http_request_sent'])
    try:curl=json.loads(parts['metadata'])
    except (ValueError,UnicodeError):curl={}
    if not isinstance(curl,dict):curl={}
    status=curl.get('http_code')if type(curl.get('http_code'))is int else None
    try:status,headers=_headers(parts['headers'])
    except FilingError:headers={}
    response=httpx.Response(status,headers=headers,request=httpx.Request('GET',URL))if type(status)is int and 100<=status<=599 else None
    if response is not None:
        native.observe_http_response(response)
        diagnostic.update(http_status=status,http_status_observed=True)
    def fail(kind):
        diagnostic.update(error_kind=kind,http_status=status)
        exc=SourceResponseError(kind,status_code=status)
        if response is not None:exc.response=response
        if status in {401,403,429}or status and status>=500:native.remember_failure(key,exc)
        raise exc
    if status is not None and status!=200:fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
    if error or rc:fail(error or ('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
    if time.monotonic()>=stop:fail('timeout')
    wire=parts['body'];encoding=headers.get('content-encoding','identity').lower()
    try:raw=decode_wire(wire,encoding)
    except FilingError:fail('decompression_invalid')
    try:clen=int(headers['content-length'])if 'content-length'in headers else None
    except ValueError:fail('transport_metadata_invalid')
    ctype=headers.get('content-type','').split(';')[0].strip().lower()
    meta={k:curl.get(k)for k in ('http_status','url_effective','num_redirects','method','proxy_used','ssl_verify_result','size_download')}
    meta.update(http_status=curl.get('http_code'),content_type=ctype,content_encoding=encoding,content_length=clen,
                wire_bytes=len(wire),wire_sha256=sha256(wire).hexdigest(),decoded_bytes=len(raw),decoded_sha256=sha256(raw).hexdigest())
    if status!=200 or not _metadata_valid(meta,wire,raw)or curl.get('content_type','').split(';')[0].strip().lower()!=ctype:fail('transport_metadata_invalid')
    validate_page(raw)
    from bs4 import BeautifulSoup
    if 'China Airlines'not in BeautifulSoup(raw.decode('utf-8','strict'),'html.parser').get_text(' ',strip=True):_bad('visible issuer missing')
    if time.monotonic()>=stop:fail('timeout')
    stamp=time.time()
    receipt=archive_response(wire,source_url=URL,retrieved_at=stamp,http_status=200)
    receipt.update(transport_policy=POLICY,http_status_observed=True,request_method='GET',response_complete=True,cache_hit=False,cal_ir_metadata=meta,
                   decoded_original=archive_response(raw,source_url=URL,retrieved_at=stamp,http_status=None,evidence_kind='decoded_http_response_bytes'))
    receipt['cal_ir_manifest']=archive_response(json.dumps(receipt,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode(),source_url=URL,retrieved_at=stamp,http_status=None,evidence_kind='private_acquisition_manifest')
    if read_original(receipt)!=raw:_bad('readback differs')
    if time.monotonic()>=stop:fail('timeout')
    diagnostic.update(http_status=200,http_status_observed=True,status='complete',response_sha256=sha256(wire).hexdigest(),response_bytes=len(wire),decoded_response_bytes=len(raw),fetched_at_epoch=stamp)
    return raw,receipt
