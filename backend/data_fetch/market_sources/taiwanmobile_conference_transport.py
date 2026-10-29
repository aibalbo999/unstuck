"""Exact anonymous Taiwan Mobile originals with original and shorter cache deadlines."""
from hashlib import sha256
import base64
import math
import time
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import (
    ConferenceHttp as _ConferenceHttp, original_bytes as _original_bytes,
    valid_epoch, RECEIPT_FIELDS as _BASE_RECEIPT_FIELDS,
)

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://english.taiwanmobile.com/investor/index.html'
PDF_URL = 'https://english.taiwanmobile.com/english/upload/investor/2Q26_Conference_Call_transcript(withQA)_updated.pdf'
PDF_URLS = frozenset({PDF_URL})
PROVIDER = 'Taiwan Mobile official conference transcript'
RAW_TTL = 1800
PDF_LIMIT = 8 * 1024 * 1024
RECEIPT_FIELDS = _BASE_RECEIPT_FIELDS | {'fresh_until_epoch'}


def route_kind(url):
    if not isinstance(url, str):return None
    if url in PDF_URLS:return 'pdf'
    return {MASTER_URL:'master',INDEX_URL:'index'}.get(url)


def contract(url):
    kind = route_kind(url)
    if kind == 'master':return 2_500_000, {'text/csv','application/csv','application/octet-stream'}
    if kind == 'index':return 1_048_576, {'text/html','application/xhtml+xml'}
    if kind == 'pdf':return PDF_LIMIT, {'application/pdf','application/octet-stream'}
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
        raise ValueError('Taiwan Mobile saved original deadline unverified') from exc


def original_bytes(receipt, url, *, max_age=86400):
    if not isinstance(receipt,dict) or set(receipt) != RECEIPT_FIELDS or not valid_expiry(receipt):
        raise ValueError('Taiwan Mobile original expiry unverified')
    common = {k:v for k,v in receipt.items() if k != 'fresh_until_epoch'}
    raw = _original_bytes(common,url,max_age=max_age,url_contract=contract)
    if receipt['fresh_until_epoch'] != _saved_expiry(raw,url,receipt['retrieved_at']):
        raise ValueError('Taiwan Mobile receipt differs from saved original deadline')
    # Complete read/decompression/cache readback must not consume its lifetime.
    if not valid_epoch(receipt['retrieved_at'],max_age) or not valid_expiry(receipt):
        raise ValueError('Taiwan Mobile original expired during archive readback')
    return raw


class ConferenceHttp(_ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'taiwanmobile-transcript-raw:v1:'
    admission_prefix = 'taiwanmobile-transcript-admission:v1:'

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
        raw,receipt = super().get_receipt(url)
        if not valid_epoch(receipt['retrieved_at'],RAW_TTL) or not valid_expiry(receipt):
            raise SourceResponseError('original_expired')
        if time.monotonic() >= self.deadline:raise SourceResponseError('timeout')
        return raw,receipt
