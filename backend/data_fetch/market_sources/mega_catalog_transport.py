"""Bounded anonymous GET originals; only observed catalogue options authorize years."""
from hashlib import sha256
import json
import os
import re
import time

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError,scope_key,cooldown_state,remember_failure,observe_http_response
from shared_provider_cache import _shared_lock
from mops_material_transport import _headers,PROXY_ENV
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER
from .mega_annual_catalog import ROOT,LIMIT,POLICY,parse_page,page_url


def _manifest(receipt):
    return json.dumps({k:v for k,v in receipt.items()if k!='acquisition_manifest'},
        sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()


def original_bytes(receipt,url,*,root_sha=None):
    fields={'status','source_url','retrieved_at','http_status','raw_response_sha256','raw_response_path',
        'raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed',
        'request_method','response_complete','http_status_observed','cache_hit','policy',
        'option_discovery_sha256','response_metadata','acquisition_manifest'}
    if (not isinstance(receipt,dict)or set(receipt)!=fields or receipt.get('status')!='archived'
            or receipt.get('source_url')!=url or type(receipt.get('http_status'))is not int
            or receipt['http_status']!=200 or receipt.get('request_method')!='GET'
            or receipt.get('response_complete')is not True or receipt.get('http_status_observed')is not True
            or receipt.get('cache_hit')is not False or receipt.get('policy')!=POLICY
            or receipt.get('option_discovery_sha256')!=root_sha
            or receipt.get('evidence_kind')!='raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified')is not False
            or receipt.get('finality_guaranteed')is not False):raise ValueError('Mega original receipt invalid')
    from .mops_public_annual import _receipt
    raw=_receipt(receipt,url,LIMIT)
    m=receipt.get('response_metadata')
    if (not isinstance(m,dict)or set(m)!={'http_status','effective_url','num_redirects','proxy_used','size_download','content_type','content_length','method'}
            or type(m['http_status'])is not int or m['http_status']!=200 or m['effective_url']!=url
            or type(m['num_redirects'])is not int or m['num_redirects']!=0
            or type(m['proxy_used'])is not int or m['proxy_used']!=0 or m['method']!='GET'
            or type(m['size_download'])not in(int,float)or m['size_download']!=len(raw)
            or m['content_type']not in('text/html','application/xhtml+xml')
            or m['content_length']is not None and(type(m['content_length'])is not int or m['content_length']!=len(raw))):
        raise ValueError('Mega complete original metadata invalid')
    proof=receipt.get('acquisition_manifest')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url or proof.get('retrieved_at')!=receipt['retrieved_at']
            or proof.get('http_status')is not None or proof.get('evidence_kind')!='private_acquisition_manifest'
            or type(proof.get('raw_response_bytes'))is not int or proof['raw_response_bytes']!=len(_manifest(receipt))
            or proof.get('historical_point_in_time_verified')is not False or proof.get('finality_guaranteed')is not False
            or read_response(proof,max_bytes=16384)!=_manifest(receipt)):
        raise ValueError('Mega original immutable metadata mismatch')
    return raw


class MegaCatalogHttp:
    def __init__(self,deadline):
        self.deadline=deadline;self.components=[];self.http_request_count=0
        self._authorized={ROOT};self._root_sha=None

    def _check(self):
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')

    def get_receipt(self,url):
        if url not in self._authorized:raise SourceResponseError('unpublished_catalogue_request')
        self._check();diag={'url':url,'request_method':'GET','http_request_sent':False,'cache_hit':False,'response_complete':False}
        self.components.append(diag)
        key=scope_key(HTTP_PROVIDER,endpoint='www.megaholdings.com.tw')
        if cooldown_state(key):raise SourceResponseError('cooldown')
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':raise SourceResponseError('test_network_disabled')
        if proxy_url_for_request(url,HTTP_PROVIDER)or any(os.getenv(k)for k in PROXY_ENV):raise SourceResponseError('proxy_configuration_unsupported')
        with _shared_lock(sha256((POLICY+':'+url).encode()).hexdigest(),min(1,max(0,self.deadline-time.monotonic())))as owns:
            if not owns:raise SourceResponseError('single_flight_busy')
            self._check();stop=min(self.deadline,time.monotonic()+5);left=stop-time.monotonic()
            argv=['/usr/bin/curl','--disable','--silent','--proto','=https','--noproxy','*','--max-time',str(left),
                '--connect-timeout',str(min(2,left)),'--max-filesize',str(LIMIT),'--max-redirs','0','--retry','0',
                '--dump-header','/dev/fd/{HEADER_FD}','--write-out','%{stderr}%{json}',url]
            parts,rc,error=collect_capped_process(argv,stop,body_limit=LIMIT,headers=True)
            raw=parts.get('body',b'');status,headers,invalid=_headers(parts.get('headers',b''))
            try:native=json.loads(parts.get('metadata',b''))
            except (ValueError,UnicodeError):native={}
            if not isinstance(native,dict):native={}
            if status is None and type(native.get('http_code'))is int and 100<=native['http_code']<=599:status=native['http_code']
            diag.update(http_request_sent=parts.get('process_started')is True,http_status=status,http_status_observed=status is not None,
                response_bytes=len(raw),response_sha256=sha256(raw).hexdigest())
            self.http_request_count+=int(diag['http_request_sent'])
            response=httpx.Response(status,headers=headers,request=httpx.Request('GET',url))if status is not None else None
            if response is not None:observe_http_response(response)
            def fail(kind):
                # Preserve bounded failed bytes too; this is never an admitted
                # catalogue receipt and cannot be promoted by the consumer.
                if raw:diag['failure_evidence']=archive_response(raw,source_url=url,retrieved_at=time.time(),http_status=status,max_bytes=LIMIT)
                diag['error_kind']=kind;exc=SourceResponseError(kind,status_code=status);exc.diagnostic.update(diag)
                if response is not None:exc.response=response
                if diag['http_request_sent']:remember_failure(key,exc)
                raise exc
            if status not in(None,200):fail({401:'authentication',403:'access_denied',429:'rate_limited'}.get(status,'server_error'if status>=500 else'http_error'))
            if error or rc:fail(error or('timeout'if rc==28 else'response_too_large'if rc==63 else'transport_error'))
            length=headers.get('content-length')
            if length is not None and not re.fullmatch('[0-9]{1,20}',length):fail('transport_metadata_invalid')
            meta={'http_status':native.get('http_code'),'effective_url':native.get('url_effective'),
                'num_redirects':native.get('num_redirects'),'proxy_used':native.get('proxy_used'),
                'size_download':native.get('size_download'),'content_type':headers.get('content-type','').split(';')[0].strip().lower(),
                'content_length':int(length)if length is not None else None,'method':native.get('method')}
            if (invalid or not diag['http_request_sent']or status!=200 or meta['http_status']!=200
                    or meta['effective_url']!=url or meta['num_redirects']!=0 or meta['proxy_used']!=0 or meta['method']!='GET'
                    or not 0<len(raw)<=LIMIT or meta['size_download']!=len(raw)
                    or meta['content_length']not in(None,len(raw))or meta['content_type']not in('text/html','application/xhtml+xml')
                    or headers.get('content-encoding','identity').lower()not in('','identity')
                    or parts.get('body_bytes_read',len(raw))!=len(raw)):fail('transport_metadata_invalid')
            if time.monotonic()>=stop:fail('timeout')
            stamp=time.time();receipt=archive_response(raw,source_url=url,retrieved_at=stamp,http_status=200,max_bytes=LIMIT)
            receipt.update(request_method='GET',response_complete=True,http_status_observed=True,cache_hit=False,
                policy=POLICY,option_discovery_sha256=None if url==ROOT else self._root_sha,response_metadata=meta)
            receipt['acquisition_manifest']=archive_response(_manifest(receipt),source_url=url,retrieved_at=stamp,
                evidence_kind='private_acquisition_manifest',http_status=None)
            if original_bytes(receipt,url,root_sha=None if url==ROOT else self._root_sha)!=raw:fail('original_unverified')
            if url==ROOT:
                options=parse_page(raw,stamp)['options'];self._root_sha=receipt['raw_response_sha256']
                self._authorized.update(page_url(identifier)for identifier in options.values())
            self._check();diag.update(response_complete=True,original_receipt=receipt,fetched_at_epoch=stamp)
            return raw,receipt
