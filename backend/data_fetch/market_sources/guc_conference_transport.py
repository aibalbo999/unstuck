"""Anonymous official Guc index and linked PDFs, with shared master proof."""
import re
import base64
from hashlib import sha256
import time
from shared_provider_cache import _shared_lock
from urllib.parse import urlsplit, parse_qsl
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp, original_bytes as _read
from .conference_issuer_master import MASTER_URL, JSON_URL, request_master, read_master

INDEX_URL = 'https://www.guc-asic.com/en/investor/financial'
PROVIDER = 'GUC official conference presentation'


def pdf_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        from datetime import date
        u = urlsplit(value)
        m = re.fullmatch(r'/upload/(20[0-9]{2})_([0-9]{2})_([0-9]{2})/[0-9]{1,4}_([0-9]{14})[A-Za-z0-9]{1,64}\.pdf', u.path)
        if not m or u.scheme != 'https' or u.netloc != 'www.guc-asic.com' or u.query or u.fragment:
            return False
        day = date(*map(int,m.groups()[:3]))
        return m[4].startswith(day.strftime('%Y%m%d'))
    except (ValueError,TypeError):
        return False


def contract(url):
    if url == MASTER_URL:
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if url == INDEX_URL:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if pdf_url(url):
        return 8_000_000, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL, JSON_URL):
        return read_master(receipt, url, lambda *a, **k: _read(*a, **k, url_contract=contract), max_age=max_age)
    return _read(receipt, url, max_age=max_age, url_contract=contract)


class GucConferenceHttp(ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'guc-conference-raw:v1:'
    admission_prefix = 'guc-conference-admission:v1:'

    def get_receipt(self, url):
        if url == MASTER_URL:
            return request_master(self)
        if url != INDEX_URL:
            return super().get_receipt(url)
        # Reacquire the issuer index on each collection under the
        # existing lock; the private archive is provenance, never an HTTP hit.
        limit,_ = contract(url)
        diagnostic={'url':url,'http_request_sent':False,'cache_hit':False}
        self.components.append(diagnostic)
        def check():
            if time.monotonic() >= self.deadline:raise SourceResponseError('timeout')
        check()
        digest=sha256((self.raw_cache_prefix+url).encode()).hexdigest()
        with _shared_lock(digest,min(1.,max(0.,self.deadline-time.monotonic()))) as acquired:
            check()
            if not acquired:raise SourceResponseError('single_flight_busy')
            value=self._download(url,diagnostic)
            check()
            if (not isinstance(value,dict) or value.get('url') != url
                    or type(value.get('http_status')) is not int or value['http_status'] != 200
                    or value.get('request_method') != 'GET' or value.get('response_complete') is not True
                    or value.get('http_status_observed') is not True):
                raise SourceResponseError('original_unverified')
            encoded=value.get('body_b64')
            if not isinstance(encoded,str) or len(encoded) > (limit+2)//3*4:
                raise SourceResponseError('original_unverified')
            raw=base64.b64decode(encoded,validate=True)
            if not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value.get('sha256'):
                raise SourceResponseError('original_unverified')
            receipt=self.archive_original(raw,url,value)
            receipt.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=False)
            if self.read_original(receipt,url,max_age=1800) != raw:raise SourceResponseError('original_unverified')
            diagnostic.update(fetched_at_epoch=value['fetched_at_epoch'],original_receipt=receipt,
                              http_status=200,original_http_status_observed=True)
        check()
        if self.read_original(receipt,url,max_age=1800) != raw:raise SourceResponseError('original_expired')
        return raw,receipt
