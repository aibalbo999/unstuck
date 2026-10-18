"""Exact TWSE JSON master: bounded wire decoding and truthful native metadata."""
from datetime import date, datetime
from hashlib import sha256
import base64
import json
import os
import re
import time
import zlib
from zoneinfo import ZoneInfo
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, observe_http_response
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER, PROXY_ENV
from . import official_issuer_master as shared

URL = shared.JSON_URL
MAX_BYTES = shared.MAX_BYTES
FIELDS = {'出表日期','公司代號','公司名稱','公司簡稱','外國企業註冊地國','產業別','住址','營利事業統一編號',
          '董事長','總經理','發言人','發言人職稱','代理發言人','總機電話','成立日期','上市日期','普通股每股面額',
          '實收資本額','私募股數','特別股','編制財務報表類型','股票過戶機構','過戶電話','過戶地址',
          '簽證會計師事務所','簽證會計師1','簽證會計師2','英文簡稱','英文通訊地址','傳真機號碼',
          '電子郵件信箱','網址','已發行普通股數或TDR原股發行股數'}


def decode_wire(wire, encoding):
    if not isinstance(wire,bytes) or not 0<len(wire)<=MAX_BYTES: raise ValueError('master wire size invalid')
    if encoding in ('','identity'): return wire
    if encoding!='gzip': raise ValueError('master encoding unsupported')
    try:
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        raw=decoder.decompress(wire,MAX_BYTES+1)
        if (len(raw)>MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
            raise ValueError('gzip incomplete, oversized, trailing data or multiple members')
        return raw
    except zlib.error as exc: raise ValueError('gzip CRC or framing invalid') from exc


def _pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value: raise ValueError('duplicate JSON key')
        value[key]=item
    return value


def parse_rows(raw, epoch):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES: raise ValueError('JSON master size invalid')
    try:
        rows=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON nonfinite constant')))
    except (RecursionError,UnicodeDecodeError) as exc: raise ValueError('invalid JSON structure') from exc
    if (not isinstance(rows,list) or not 500<=len(rows)<=2000
            or any(not isinstance(r,dict) or set(r)!=FIELDS or any(not isinstance(v,str) for v in r.values()) for r in rows)):
        raise ValueError('incomplete JSON master shape')
    codes=[r['公司代號'] for r in rows]
    if len(set(codes))!=len(codes) or any(not re.fullmatch(r'\d{4,6}',c) for c in codes):raise ValueError('JSON code list invalid')
    days={r['出表日期'] for r in rows}
    if len(days)!=1 or not re.fullmatch(r'\d{7}',next(iter(days))):raise ValueError('JSON uniform date invalid')
    text=next(iter(days));day=date(int(text[:3])+1911,int(text[3:5]),int(text[5:]))
    if not 0<epoch or not 0<=(datetime.fromtimestamp(epoch,ZoneInfo('Asia/Taipei')).date()-day).days<=14:
        raise ValueError('JSON original date invalid')
    return rows


def valid_metadata(meta,raw):
    try:
        shared._cache_policy(meta)
        return (isinstance(meta,dict) and set(meta)==shared.META_FIELDS
                and type(meta['http_status']) is int and meta['http_status']==200
                and meta['effective_url']==URL and meta['method']=='GET'
                and type(meta['num_redirects']) is int and meta['num_redirects']==0
                and type(meta['proxy_used']) is int and meta['proxy_used']==0
                and type(meta['wire_bytes']) is int and 0<meta['wire_bytes']<=MAX_BYTES
                and shared._number(meta['size_download']) and meta['size_download']==meta['wire_bytes']
                and (meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length']==meta['wire_bytes'])
                and meta['content_type']=='application/json' and meta['content_encoding'] in {'','identity','gzip'}
                and type(meta['decoded_bytes']) is int and meta['decoded_bytes']==len(raw)<=MAX_BYTES
                and meta['decoded_sha256']==sha256(raw).hexdigest()
                and isinstance(meta['wire_sha256'],str) and re.fullmatch(r'[0-9a-f]{64}',meta['wire_sha256']) is not None)
    except (ValueError,TypeError,KeyError):return False


def _wire_matches(wire,raw,meta):
    if not valid_metadata(meta,raw) or len(wire)!=meta['wire_bytes'] or sha256(wire).hexdigest()!=meta['wire_sha256']:
        raise ValueError('wire metadata mismatch')
    if decode_wire(wire,meta['content_encoding'])!=raw: raise ValueError('decoded original mismatch')


def archive_wire(value,stamp):
    encoded=value.get('wire_b64')
    if not isinstance(encoded,str) or len(encoded)>(MAX_BYTES+2)//3*4:raise ValueError('wire body invalid')
    wire=base64.b64decode(encoded,validate=True);raw=base64.b64decode(value['body_b64'],validate=True)
    _wire_matches(wire,raw,value['response_metadata'])
    return archive_response(wire,source_url=URL,retrieved_at=stamp)


def verify_wire(receipt,raw):
    proof=receipt['wire_original']
    if (not isinstance(proof,dict) or set(proof)!=shared.ARCHIVE_FIELDS
            or proof.get('status')!='archived' or proof.get('source_url')!=URL
            or not shared._number(proof.get('retrieved_at')) or proof['retrieved_at']!=receipt['retrieved_at']
            or type(proof.get('http_status')) is not int or proof['http_status']!=200
            or proof.get('evidence_kind')!='raw_http_response_bytes'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int):raise ValueError('wire archive receipt invalid')
    wire=read_response(proof,max_bytes=MAX_BYTES)
    if len(wire)!=proof['raw_response_bytes']:raise ValueError('wire archive size invalid')
    _wire_matches(wire,raw,receipt['response_metadata'])


def download_original(http,diagnostic,*,parse_headers):
    """One exact URL; curl does not decode or redirect and has no automatic retry."""
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
    if proxy_url_for_request(URL,HTTP_PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
    http._external_guards(URL)
    remaining=min(5.,http.deadline-time.monotonic())
    if remaining<=0:raise SourceResponseError('timeout')
    stop=min(http.deadline,time.monotonic()+remaining)
    args=['/usr/bin/curl','--disable','--silent','--max-time',str(remaining),'--connect-timeout',str(min(2.,remaining)),
          '--max-filesize',str(MAX_BYTES),'--proto','=https','--max-redirs','0','--retry','0',
          '--header','Accept-Encoding: gzip','--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',URL]
    parts,rc,error=collect_capped_process(args,stop,body_limit=MAX_BYTES,headers=True)
    diagnostic.update(http_request_sent=bool(parts.get('process_started')),request_method='GET',request_body=None)
    http.http_request_count+=int(diagnostic['http_request_sent'])
    try:meta=json.loads(parts['metadata'])
    except (ValueError,UnicodeDecodeError):meta={}
    if not isinstance(meta,dict):meta={}
    observed=meta.get('http_code')
    if type(observed) is int and 100<=observed<=599:diagnostic['http_status']=observed
    try:status,headers=parse_headers(parts['headers'])
    except (ValueError,SourceResponseError) as exc:raise SourceResponseError('transport_metadata_invalid',status_code=diagnostic.get('http_status')) from exc
    response=httpx.Response(status,headers=headers,request=httpx.Request('GET',URL)) if status else None
    if response is not None:observe_http_response(response)
    def fail(kind):
        diagnostic.update(error_kind=kind,http_status=status)
        exc=SourceResponseError(kind,status_code=status)
        if response is not None:exc.response=response
        if status in {401,403,429} or status and status>=500:remember_failure(scope_key(HTTP_PROVIDER,endpoint='openapi.twse.com.tw'),exc)
        raise exc
    if status is not None and status!=200:fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error' if status>=500 else 'http_error'))
    if error or rc:fail(error or ('timeout' if rc==28 else 'response_too_large' if rc==63 else 'transport_error'))
    if time.monotonic()>=stop:fail('timeout')
    wire=parts['body'];encoding=headers.get('content-encoding','identity').lower()
    try:raw=decode_wire(wire,encoding)
    except ValueError:fail('decompression_invalid')
    if time.monotonic()>=stop:fail('timeout')
    ctype=headers.get('content-type','').split(';')[0].strip().lower()
    try:clen=int(headers['content-length']) if 'content-length' in headers else None
    except (ValueError,TypeError):fail('transport_metadata_invalid')
    metadata={'http_status':meta.get('http_code'),'effective_url':meta.get('url_effective'),'num_redirects':meta.get('num_redirects'),
              'size_download':meta.get('size_download'),'content_type':ctype,'content_length':clen,'method':meta.get('method'),
              'proxy_used':meta.get('proxy_used'),'cache_control':headers.get('cache-control',''),'content_encoding':encoding,
              'wire_bytes':len(wire),'wire_sha256':sha256(wire).hexdigest(),'decoded_bytes':len(raw),'decoded_sha256':sha256(raw).hexdigest(),'age':headers.get('age')}
    if status!=200 or not valid_metadata(metadata,raw) or meta.get('content_type','').split(';')[0].strip().lower()!=ctype:fail('transport_metadata_invalid')
    diagnostic.update(http_status=200,response_bytes=len(wire),decoded_response_bytes=len(raw),response_sha256=sha256(wire).hexdigest(),response_metadata=metadata)
    return {'url':URL,'request_method':'GET','request_body':None,'body_b64':base64.b64encode(raw).decode(),
            'wire_b64':base64.b64encode(wire).decode(),'sha256':sha256(raw).hexdigest(),'response_metadata':metadata}
