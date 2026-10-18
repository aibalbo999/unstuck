"""Exact anonymous CSC originals with original and shorter cache deadlines."""
from . import conference_issuer_master as master_identity
from hashlib import sha256
import base64
import math
from datetime import date
import re
import time
from urllib.parse import parse_qsl, urlsplit
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import (
    ConferenceHttp as _ConferenceHttp, original_bytes as _original_bytes,
    valid_epoch, RECEIPT_FIELDS as _BASE_RECEIPT_FIELDS,
)

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://www.csc.com.tw/csc_e/ss/pst/pst_index.html'
PDF_URL = 'https://www.csc.com.tw/csc_e/ss/pst/pdf/2026Sep23.pdf'
CHINESE_INDEX_URL = 'https://www.csc.com.tw/csc/ss/pst/pst_index2.html'
CHINESE_PDF_URL = 'https://www.csc.com.tw/csc/ss/pst/pdf/2026Sep23.pdf'
MOPS_IIH_URL = 'https://wwwc.twse.com.tw/rwd/en/IIH/company/events?code=2002'
PROVIDER = 'CSC official conference presentation'
RAW_TTL = 1800
PDF_LIMIT = 8 * 1024 * 1024
RECEIPT_FIELDS = _BASE_RECEIPT_FIELDS | {'fresh_until_epoch'}


def route_kind(url):
    if not isinstance(url, str):
        return None
    fixed = {MASTER_URL:'master', INDEX_URL:'index', PDF_URL:'pdf',
             CHINESE_INDEX_URL:'chinese_index', CHINESE_PDF_URL:'chinese_pdf', MOPS_IIH_URL:'mops_iih'}
    if url in fixed:
        return fixed[url]
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=False, strict_parsing=True)
        query = dict(pairs)
        if (parsed.scheme == 'https' and parsed.hostname == 'emops.twse.com.tw'
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and not parsed.fragment and len(query) == len(pairs)):
            if (parsed.path == '/server-java/t100sb07_1_e'
                    and set(query) == {'TYPEK','step','code','LPSHOW_DATE_YY','LPSHOW_DATE_MM'}
                    and query.get('TYPEK') == 'all' and query.get('step') == 'show'
                    and query.get('code') == '2002'
                    and re.fullmatch(r'20\d{2}', query.get('LPSHOW_DATE_YY',''))
                    and re.fullmatch(r'0[1-9]|1[0-2]', query.get('LPSHOW_DATE_MM',''))):
                return 'mops_index'
            match = re.fullmatch(r'/nas/STR/2002(\d{8})[ME]\d{3}\.pdf', parsed.path)
            if match:
                date(int(match[1][:4]), int(match[1][4:6]), int(match[1][6:8]))
                return 'mops_pdf'
    except (TypeError, ValueError, OverflowError):
        return None
    return None


def contract(url):
    kind = route_kind(url)
    if kind == 'master':return 2_500_000, {'text/csv','application/csv','application/octet-stream'}
    if kind == 'index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind == 'pdf':return PDF_LIMIT, {'application/pdf','application/octet-stream'}
    if kind == 'chinese_index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind == 'chinese_pdf':return PDF_LIMIT, {'application/pdf','application/octet-stream'}
    if kind == 'mops_iih':return 256_000, {'application/json','text/json'}
    if kind == 'mops_index':return 256_000, {'text/html','application/xhtml+xml'}
    if kind == 'mops_pdf':return PDF_LIMIT, {'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def valid_expiry(receipt, observed=None):
    try:
        stamp,expiry = receipt['retrieved_at'],receipt['fresh_until_epoch']
        return (type(stamp) in (int,float) and type(expiry) in (int,float)
                and math.isfinite(stamp) and math.isfinite(expiry)
                and 0 < stamp < expiry <= stamp + RAW_TTL
                and stamp <= (time.time() if observed is None else observed) < expiry)
    except (ValueError,TypeError,KeyError,OverflowError):
        return False



def _saved_expiry(raw, url, original_epoch):
    """Rebind expiry to the independently stored exact original observation."""
    from cache_store import get_cache_json
    try:
        limit, _ = contract(url)
        key = 'shared_provider:v1:' + sha256((ConferenceHttp.raw_cache_prefix+url).encode()).hexdigest()
        row = get_cache_json(key)
        if not isinstance(row,dict) or set(row) != {'value','fetched_at_epoch','fresh_until_epoch','retained_until_epoch'}:
            raise ValueError('saved observation unavailable')
        for key in ('fetched_at_epoch','fresh_until_epoch','retained_until_epoch'):
            if type(row[key]) not in (int,float) or not math.isfinite(row[key]) or row[key] <= 0:
                raise ValueError('saved observation time invalid')
        value = row['value']
        if (not isinstance(value,dict) or set(value) != {'url','body_b64','sha256','http_status',
                'response_complete','request_method','http_status_observed','fetched_at_epoch'}
                or value['url'] != url or value['sha256'] != sha256(raw).hexdigest()
                or type(value['http_status']) is not int or value['http_status'] != 200
                or value['response_complete'] is not True or value['http_status_observed'] is not True
                or value['request_method'] != 'GET'
                or not valid_epoch(value['fetched_at_epoch'],RAW_TTL)
                or value['fetched_at_epoch'] != original_epoch
                or not original_epoch <= row['fetched_at_epoch'] <= time.time()
                or not row['fetched_at_epoch'] < row['fresh_until_epoch'] <= row['retained_until_epoch']):
            raise ValueError('saved original metadata mismatch')
        encoded = value['body_b64']
        if (not isinstance(encoded,str) or len(encoded) > (limit+2)//3*4
                or base64.b64decode(encoded,validate=True) != raw):
            raise ValueError('saved complete original bytes mismatch')
        return min(row['fresh_until_epoch'],original_epoch+RAW_TTL)
    except Exception as exc:
        raise ValueError('CSC saved original deadline unverified') from exc


def _legacy_original_bytes(receipt, url, *, max_age=86400):
    if not isinstance(receipt,dict) or set(receipt) != RECEIPT_FIELDS or not valid_expiry(receipt):
        raise ValueError('CSC original expiry unverified')
    common = {k:v for k,v in receipt.items() if k != 'fresh_until_epoch'}
    raw = _original_bytes(common,url,max_age=max_age,url_contract=contract)
    if receipt['fresh_until_epoch'] != _saved_expiry(raw,url,receipt['retrieved_at']):
        raise ValueError('CSC receipt differs from saved original deadline')
    # Complete read/decompression/cache readback must not consume its lifetime.
    if not valid_epoch(receipt['retrieved_at'],max_age) or not valid_expiry(receipt):
        raise ValueError('CSC original expired during archive readback')
    return raw


def is_legacy_master(receipt):
    # CSC v1 already had fresh_until_epoch; that field alone is not shared proof.
    return (isinstance(receipt,dict) and set(receipt)==RECEIPT_FIELDS
            and receipt.get('source_url')==MASTER_URL)


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL,master_identity.JSON_URL):
        if is_legacy_master(receipt):
            return _legacy_original_bytes(receipt,url,max_age=max_age)
        # Preserve CSC's existing <=1800s/shorter-physical-TTL replay gate,
        # including callers using the old 86400 max_age default.
        return master_identity.read_master(receipt,url,_legacy_original_bytes,max_age=min(max_age,RAW_TTL))
    return _legacy_original_bytes(receipt,url,max_age=max_age)


class ConferenceHttp(_ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'csc-conference-raw:v1:'
    admission_prefix = 'csc-conference-admission:v1:'

    def request_timeout_seconds(self, url):
        # The official CSC index timed out under the generic 5 s page limit.
        # Widen only that HTML entry point; the shared MOPS roster keeps its
        # existing 8 s budget and the conference PDF keeps the 5 s cap.
        return 8. if url == INDEX_URL else super().request_timeout_seconds(url)

    def connect_timeout_seconds(self, url):
        return 6. if url == INDEX_URL else super().connect_timeout_seconds(url)

    def archive_original(self, raw, url, value):
        # Read the actual row rather than reconstructing a TTL from receipt time.
        # This same independent observation is required on every later replay.
        try:
            expiry = _saved_expiry(raw,url,value['fetched_at_epoch'])
        except (ValueError,KeyError,TypeError) as exc:
            raise SourceResponseError('cache_receipt_invalid') from exc
        receipt = super().archive_original(raw,url,value)
        if receipt.get('status') != 'archived':raise SourceResponseError('original_unverified')
        receipt['fresh_until_epoch'] = expiry
        if not valid_expiry(receipt):raise SourceResponseError('original_expired')
        return receipt

    def read_original(self, receipt, url, *, max_age):
        return original_bytes(receipt,url,max_age=max_age)

    def get_receipt(self, url):
        raw,receipt = (master_identity.request_master(self) if url==MASTER_URL
                       else super().get_receipt(url))
        if not valid_epoch(receipt['retrieved_at'],RAW_TTL) or not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        if time.monotonic() >= self.deadline:raise SourceResponseError('timeout')
        return raw,receipt
