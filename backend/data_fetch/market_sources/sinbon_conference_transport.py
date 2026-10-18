"""Sinbon exact public POSTs; immutable original receipts, no success cache reuse."""
import base64
from hashlib import sha256
import json
import math
import os
import re
import time
from urllib.parse import urlsplit
from uuid import uuid4
from datetime import datetime
from zoneinfo import ZoneInfo
from mops_material_transport import index_request, download_conference_index, download_published_material, validate_response_metadata
from mops_material_originals import _guard as mops_guard, GUARD
from search_admission import endpoint_admission
from .tecom_conference_transport import ConferenceHttp as _MasterDelegate, _metadata_valid as _master_metadata_valid
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, remember_success, observe_http_response
from shared_provider_cache import _shared_lock
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER, PROXY_ENV
from . import official_issuer_master
from .official_issuer_master_transport import IssuerMasterHttp
from .tcfhc_conference_transport import ConferenceHttp as _ConferenceHttp, valid_epoch, RECEIPT_FIELDS as BASE_FIELDS

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://mopsov.twse.com.tw/mops/web/ajax_t100sb02_1'
PDF_URL = 'https://mopsov.twse.com.tw/server-java/FileDownLoad'
PROVIDER = 'Sinbon published conference presentation'
RAW_TTL = 1800
RECEIPT_FIELDS = BASE_FIELDS | {'fresh_until_epoch','request_body','response_metadata','acquisition_manifest','retrieval_policy'}
VALUE_FIELDS = {'url','body_b64','sha256','http_status','response_complete','request_method','request_body',
                'http_status_observed','fetched_at_epoch','response_metadata'}
META_FIELDS = {'http_status','effective_url','num_redirects','size_download','content_type','content_length','method','proxy_used','cache_control','pragma','expires','age','cf_cache_status'}


def _headers(raw):
    """Preserve final response lengths; reject ambiguous protected headers."""
    status=None;headers={}
    for line in raw.replace(b'\r\n',b'\n').splitlines():
        if line.startswith(b'HTTP/'):
            match=re.fullmatch(rb'HTTP/[^ ]+ +([1-5][0-9]{2})(?: .*)?',line)
            if not match:raise SourceResponseError('transport_metadata_invalid')
            status=int(match[1]);headers={}
        elif line and status:
            key,sep,value=line.partition(b':')
            if not sep:raise SourceResponseError('transport_metadata_invalid')
            name=key.decode('ascii','strict').lower()
            if name in {'content-length','content-type','content-encoding','retry-after','cache-control','location','age','pragma','expires','cf-cache-status'}:
                if name in headers:raise SourceResponseError('transport_metadata_invalid')
                headers[name]=value.decode('latin-1').strip()
    return status,headers


def route_kind(url):
    return {MASTER_URL:'master',INDEX_URL:'index',PDF_URL:'pdf'}.get(url) if isinstance(url,str) else None


def contract(url):
    kind=route_kind(url)
    if kind=='master':return 2_500_000, {'text/csv','application/csv','application/octet-stream'}
    if kind=='index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind=='pdf':return 8*1024*1024, {'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def request_spec(url, epoch=None):
    contract(url)
    if url==MASTER_URL:return {'request_method':'GET','request_body':None}
    spec=_descriptor(url,epoch)
    return {'request_method':'POST','request_body':spec['request_body']}


def _descriptor(url, epoch=None):
    if url==INDEX_URL:
        year=datetime.fromtimestamp(time.time()if epoch is None else epoch,ZoneInfo('Asia/Taipei')).year
        return index_request('3023.TW',year)
    if url==PDF_URL:return dict(PUBLISHED_DOWNLOAD)
    raise SourceResponseError('transport_url_invalid')


def validation_ttl(meta):
    return RAW_TTL


def valid_expiry(receipt, observed=None):
    try:
        stamp,expiry=receipt['retrieved_at'],receipt['fresh_until_epoch']
        return (type(stamp) in (int,float) and type(expiry) in (int,float) and math.isfinite(stamp) and math.isfinite(expiry)
                and 0<stamp<expiry<=stamp+RAW_TTL and expiry==stamp+validation_ttl(receipt['response_metadata']) and stamp<=(time.time() if observed is None else observed)<expiry)
    except (ValueError,TypeError,KeyError,OverflowError):return False


def replay_expiry_valid(receipt, max_age, observed=None):
    # 1800 seconds is the live delivery deadline, not permission to reuse HTTP.
    # Longer replay only proves an immutable historical acquisition; it cannot
    # feed get_receipt(), which always performs a new native request.
    if isinstance(receipt,dict) and receipt.get('retrieval_policy') in (official_issuer_master.POLICY,official_issuer_master.JSON_POLICY):
        return official_issuer_master.live_or_historical_expiry_valid(receipt,max_age,observed)
    at = time.time() if observed is None else observed
    return valid_expiry(receipt, at if max_age <= RAW_TTL else receipt.get('retrieved_at'))


def _metadata_valid(meta,raw,url):
    if url==MASTER_URL:return _master_metadata_valid(meta,raw,url)
    return validate_response_metadata(meta,raw,_descriptor(url))


class ConferenceHttp(_ConferenceHttp):
    route_contract=staticmethod(contract)
    # Exact request-bound anonymous MOPS POSTs and a shared official master GET.
    raw_cache_prefix='sinbon-conference-raw:v1:POST:'
    admission_prefix='sinbon-conference-admission:v1:POST:'

    _guarded_download = IssuerMasterHttp._guarded_download

    def _check(self):
        if time.monotonic()>=self.deadline:raise SourceResponseError('timeout')

    def _external_guards(self,url):
        if url not in {INDEX_URL,PDF_URL}:
            return _MasterDelegate._external_guards(self,url)
        mops_guard(_descriptor(url),self.deadline,getattr(self,'_owns',None))
        self._check()

    def check_index_guard(self):
        mops_guard(_descriptor(INDEX_URL),self.deadline,None)
        self._check()

    def download_original(self,url,diagnostic):
        if url in {MASTER_URL,official_issuer_master.JSON_URL}:
            return _MasterDelegate.download_original(self,url,diagnostic)
        self._external_guards(url)
        spec=_descriptor(url)
        diagnostic['request_started_at']=time.time()
        try:
            if url==INDEX_URL:
                raw=download_conference_index('3023.TW',year=spec['year'],deadline=self.deadline,diagnostics=diagnostic)
            else:raw=download_published_material(spec,deadline=self.deadline,diagnostics=diagnostic)
        except SourceResponseError as exc:
            if diagnostic.get('http_request_sent') is True and getattr(self,'_owns',lambda:False)():
                remember_failure(GUARD,exc)
            raise
        finally:self.http_request_count+=int(diagnostic.get('http_request_sent')is True)
        self._check()
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                **request_spec(url),'response_metadata':diagnostic['response_metadata']}

    def _download(self,url,diagnostic):
        self._check();self._retry_guard(url);self._external_guards(url)
        from cache_store import get_cache_json,set_cache_json
        key=self._admission_key(url);marker={'token':uuid4().hex,'retry_at':time.time()+120}
        try:
            set_cache_json(key,marker,ttl_seconds=120)
            if get_cache_json(key)!=marker:raise SourceResponseError('lease_lost')
        except SourceResponseError:raise
        except Exception as exc:raise SourceResponseError('guard_storage_unavailable') from exc
        self._check()
        value=self.download_original(url,diagnostic)
        fetched_at=time.time()
        self._check()
        try:
            if get_cache_json(key)==marker:set_cache_json(key,{**marker,'retry_at':0},ttl_seconds=1)
        except Exception:diagnostic['admission_release_failed']=True
        self._check()
        return {**value,'http_status':200,'response_complete':True,'http_status_observed':True,'fetched_at_epoch':fetched_at}

    def get_receipt(self,url,*,parser=None):
        """Parse under admission; only validated native content ends a failure streak."""
        if url==MASTER_URL:return IssuerMasterHttp.get_receipt(self,url)
        with endpoint_admission(GUARD,timeout_seconds=max(0.,self.deadline-time.monotonic()))as owns:
            if owns is None:raise SourceResponseError('single_flight_busy')
            self._owns=owns
            try:
                self._external_guards(url)
                raw,receipt=self._get_receipt(url)
                diagnostic=self.components[-1]
                parsed=parser(raw,receipt) if parser is not None else raw
                self._check()
                if not owns():raise SourceResponseError('lease_lost')
                if parser is not None and diagnostic.get('http_request_sent') is True and not receipt['cache_hit']:
                    remember_success(GUARD,request_started_at=diagnostic.get('request_started_at'))
                self._check()
                if not owns():raise SourceResponseError('lease_lost')
                return parsed,receipt
            finally:self._owns=None

    def _get_receipt(self, url):
        if url == MASTER_URL:
            return IssuerMasterHttp.get_receipt(self,url)
        limit, _ = contract(url)
        diagnostic = {'url': url, 'http_request_sent': False, 'cache_hit': False, **request_spec(url)}
        self.components.append(diagnostic)
        self._check()
        # A lock serializes acquisition, but never supplies an earlier response.
        digest = sha256((self.raw_cache_prefix + url).encode()).hexdigest()
        with _shared_lock(digest, min(1., max(0., self.deadline-time.monotonic()))) as acquired:
            self._check()
            if not acquired:
                raise SourceResponseError('single_flight_busy')
            value = self._download(url, diagnostic)
            self._check()
            raw = base64.b64decode(value['body_b64'], validate=True)
            if (not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value['sha256']
                    or not _metadata_valid(value['response_metadata'], raw, url)):
                raise SourceResponseError('transport_metadata_invalid')
            stamp = value['fetched_at_epoch']
            receipt = archive_response(raw, source_url=url, retrieved_at=stamp)
            if receipt.get('status') != 'archived':
                raise SourceResponseError('original_unverified')
            receipt.update(http_status_observed=True, **request_spec(url,stamp),
                           response_complete=True, cache_hit=False, fresh_until_epoch=stamp+validation_ttl(value['response_metadata']),
                           response_metadata=value['response_metadata'],
                           retrieval_policy='always_native_no_success_cache')
            # Immutable manifest binds the original epoch and validation deadline.
            # It is provenance for saved reports, never an HTTP/cache response.
            manifest = _manifest_bytes(receipt)
            receipt['acquisition_manifest'] = archive_response(
                manifest, source_url=url, retrieved_at=stamp,
                evidence_kind='private_acquisition_manifest', http_status=None)
            if original_bytes(receipt, url, max_age=RAW_TTL) != raw:
                raise SourceResponseError('original_unverified')
            self._check()
            diagnostic.update(fetched_at_epoch=stamp, original_receipt=receipt,
                              http_status=200, original_http_status_observed=True)
        # Lock cleanup and final delivery are part of this request's budget.
        self._check()
        if not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        return raw, receipt


def _manifest_bytes(receipt):
    return json.dumps({k:v for k,v in receipt.items() if k != 'acquisition_manifest'},
                      sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode()


def original_bytes(receipt, url, *, max_age=86400):
    if url == official_issuer_master.JSON_URL:
        if not isinstance(receipt,dict) or receipt.get('source_url') != url:
            raise ValueError('JSON master URL mismatch')
        return official_issuer_master.original_bytes(receipt,max_age=max_age)
    if url == MASTER_URL and isinstance(receipt,dict) and receipt.get('retrieval_policy') == official_issuer_master.POLICY:
        return official_issuer_master.original_bytes(receipt,max_age=max_age)
    limit, _ = contract(url)
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS
            or receipt.get('status') != 'archived' or receipt.get('source_url') != url
            or receipt.get('cache_hit') is not False or receipt.get('request_method') != request_spec(url,receipt.get('retrieved_at'))['request_method']
            or receipt.get('request_body') != request_spec(url,receipt.get('retrieved_at'))['request_body'] or receipt.get('response_complete') is not True
            or receipt.get('http_status_observed') is not True or type(receipt.get('http_status')) is not int
            or receipt['http_status'] != 200 or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or receipt.get('retrieval_policy') != 'always_native_no_success_cache'
            or not valid_epoch(receipt.get('retrieved_at'), max_age) or not replay_expiry_valid(receipt,max_age)):
        raise ValueError('Sinbon original receipt unverified')
    raw = read_response(receipt)
    if (type(receipt.get('raw_response_bytes')) is not int or not 0 < len(raw) <= limit
            or len(raw) != receipt['raw_response_bytes'] or not _metadata_valid(receipt['response_metadata'], raw, url)):
        raise ValueError('Sinbon original metadata mismatch')
    proof = receipt['acquisition_manifest']
    if (not isinstance(proof, dict) or set(proof) != BASE_FIELDS - {'http_status_observed','request_method','response_complete','cache_hit'}
            or proof.get('status') != 'archived' or proof.get('source_url') != url
            or type(proof.get('retrieved_at')) not in (int,float) or proof['retrieved_at'] != receipt['retrieved_at']
            or proof.get('http_status') is not None or proof.get('evidence_kind') != 'private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int):
        raise ValueError('Sinbon independent acquisition manifest invalid')
    manifest = read_response(proof, max_bytes=16384)
    if len(manifest) != proof['raw_response_bytes'] or manifest != _manifest_bytes(receipt):
        raise ValueError('Sinbon original epoch/deadline differs from immutable acquisition manifest')
    if not valid_epoch(receipt['retrieved_at'],max_age) or not replay_expiry_valid(receipt,max_age):
        raise ValueError('Sinbon original expired during archive replay')
    return raw

PUBLISHED_DOWNLOAD = {'ticker': '3023.TW', 'symbol': '3023', 'company_name': '信邦', 'event_date': '2026-09-15', 'event_end_date': '2026-09-15', 'event_time': '09:00', 'event_location': 'UBS Taiwan Summit 2026', 'event_summary': '公告本公司受邀參加UBS Taiwan Summit 2026', 'material_file_date': '2026-09-09', 'filename': '302320260909E001.pdf', 'format': 'pdf', 'language': 'en', 'index_sha256': '79739f4c49706bc204925806e88de45b9f3988ee72236924d7c52963744bb76f', 'row_sha256': '3dc80827b0007cdaf0b53c0ccfc64d538236cc82903eebec2bc36058b80f4d49', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=302320260909E001.pdf&functionName=t100sb02_1', 'request_sha256': '9363189329cd0a2d93a3cb30b29929a7b6c522a91ae09952256c58e940f6cf80'}
