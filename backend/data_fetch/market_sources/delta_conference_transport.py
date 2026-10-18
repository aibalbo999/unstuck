"""Reuse guarded original-byte transport for the published Delta transcript."""
from . import conference_issuer_master as master_identity
import re
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp as BaseHttp, original_bytes as read_original, RAW_TTL

MASTER_URL='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX_URL='https://www.deltaww.com/en-US/investors/analyst-meeting'
PROVIDER='Delta official translated conference transcript'
PDF=re.compile(r'https://filecenter\.deltaww\.com/IR/download/calendar/[1-4]Q\d{2}_Transcript\.pdf')

def route_kind(url):
    if url==MASTER_URL:return 'master'
    if url==INDEX_URL:return 'index'
    if isinstance(url,str)and PDF.fullmatch(url):return 'transcript'
    return None

def contract(url):
    kind=route_kind(url)
    if kind=='master':return 2_500_000,{'text/csv','application/csv','application/octet-stream'}
    if kind=='index':return 1_000_000,{'text/html','application/xhtml+xml'}
    if kind=='transcript':return 1_000_000,{'application/pdf','application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')

def _legacy_original_bytes(receipt,url,*,max_age=86400):
    return read_original(receipt,url,max_age=max_age,url_contract=contract)


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL, master_identity.JSON_URL):
        return master_identity.read_master(receipt, url, _legacy_original_bytes, max_age=max_age)
    return _legacy_original_bytes(receipt, url, max_age=max_age)

class ConferenceHttp(BaseHttp):
    route_contract=staticmethod(contract)
    raw_cache_prefix='delta-transcript-raw:v1:'
    admission_prefix='delta-transcript-admission:v1:'

    def get_receipt(self, url):
        if url == MASTER_URL:
            return master_identity.request_master(self)
        return super().get_receipt(url)
