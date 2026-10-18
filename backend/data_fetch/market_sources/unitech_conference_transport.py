"""Exact anonymous Unitech originals using the existing guarded raw transport."""
from . import conference_issuer_master as master_identity
import time
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp as _ConferenceHttp, original_bytes as _original_bytes, valid_epoch

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL = 'https://www.pcbut.com.tw/portal/IP/5/IN5_3.html'
PDF_URL = 'https://www.pcbut.com.tw/downloads/InvestorConference2026.pdf'
PROVIDER = 'Unitech official conference presentation'
RAW_TTL = 1800
PDF_LIMIT = 8 * 1024 * 1024


def route_kind(url):
    return {MASTER_URL: 'master', INDEX_URL: 'index', PDF_URL: 'pdf'}.get(url) if isinstance(url, str) else None


def contract(url):
    kind = route_kind(url)
    if kind == 'master':
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if kind == 'index':
        return 200_000, {'text/html', 'application/xhtml+xml'}
    if kind == 'pdf':
        return PDF_LIMIT, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def _legacy_original_bytes(receipt, url, *, max_age=86400):
    raw = _original_bytes(receipt, url, max_age=max_age, url_contract=contract)
    # Decompression/readback cannot extend the original acquisition lifetime.
    if not valid_epoch(receipt['retrieved_at'], max_age):
        raise ValueError('Unitech original expired during archive readback')
    return raw


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL, master_identity.JSON_URL):
        return master_identity.read_master(receipt, url, _legacy_original_bytes, max_age=max_age)
    return _legacy_original_bytes(receipt, url, max_age=max_age)


class ConferenceHttp(_ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'unitech-conference-raw:v1:'
    admission_prefix = 'unitech-conference-admission:v1:'

    def read_original(self, receipt, url, *, max_age):
        return original_bytes(receipt, url, max_age=max_age)

    def get_receipt(self, url):
        if url == MASTER_URL:
            return master_identity.request_master(self)
        raw, receipt = super().get_receipt(url)
        if not valid_epoch(receipt['retrieved_at'], RAW_TTL):
            raise SourceResponseError('original_expired')
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw, receipt
