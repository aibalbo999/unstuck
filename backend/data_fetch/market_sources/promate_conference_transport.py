"""Anonymous official Promate index and linked PDFs, with shared master proof."""
import re
from urllib.parse import urlsplit, unquote
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp, original_bytes as _read
from .conference_issuer_master import MASTER_URL, JSON_URL, request_master, read_master

INDEX_URL = 'https://www.promate.com.tw/investors-relations/investor-conference/'
PROVIDER = 'Promate official conference presentation'


def pdf_url(value):
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    path = unquote(u.path)
    return (u.scheme == 'https' and u.netloc == 'www.promate.com.tw' and not u.query and not u.fragment
            and re.fullmatch(r'/wp-content/uploads/(?:20\d{2}/\d{2}/)?[\w\-]+\.pdf', path) is not None
            and '%' not in path)


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


class PromateConferenceHttp(ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'promate-conference-raw:v1:'
    admission_prefix = 'promate-conference-admission:v1:'

    def get_receipt(self, url):
        if url == MASTER_URL:
            return request_master(self)
        return super().get_receipt(url)
