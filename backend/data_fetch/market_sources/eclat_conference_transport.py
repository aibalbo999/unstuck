"""Bounded ordinary HTTPS for Eclat's published event index and linked slides."""
import re

from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp, original_bytes as _read
from .conference_issuer_master import MASTER_URL, JSON_URL, request_master, read_master

INDEX_URL = 'https://www.eclat.com.tw/investors/events-presentations/'
PROVIDER = 'Eclat official conference presentation'
PDF_URL = re.compile(r'https://eclatglobal\.s3\.amazonaws\.com/uploads/(20\d{2})/(0[1-9]|1[0-2])/\1_eclat_Investor-Conference-Slides_Q([1-4])_en\.pdf\Z')


def pdf_url(url):
    return isinstance(url, str) and PDF_URL.fullmatch(url) is not None


def contract(url):
    if url == INDEX_URL:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if pdf_url(url):
        return 8_000_000, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def original_bytes(receipt, url, *, max_age=1800):
    if url in (MASTER_URL, JSON_URL):
        return read_master(receipt, url, lambda *a, **k: _read(*a, **k), max_age=max_age)
    return _read(receipt, url, max_age=max_age, url_contract=contract)


class EclatConferenceHttp(ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'eclat-conference-raw:v1:'
    admission_prefix = 'eclat-conference-admission:v1:'

    def __init__(self, deadline, **options):
        super().__init__(deadline, **options)
        self._index = None
        self._authorized = set()

    def get_receipt(self, url):
        if url == MASTER_URL:
            return request_master(self)
        if url == INDEX_URL:
            # Recheck the live event list on every acquisition, even with a
            # reusable PDF; a stored presentation must not hide a new event.
            previous = self.force_refresh
            self.force_refresh = True
            try:
                raw, receipt = super().get_receipt(url)
            finally:
                self.force_refresh = previous
            self._index = receipt
            return raw, receipt
        if url not in self._authorized:
            raise SourceResponseError('transport_url_invalid')
        return super().get_receipt(url)

    def authorize_index(self, receipt):
        from .eclat_conference import select_presentation
        if receipt != self._index:
            raise SourceResponseError('original_unverified')
        selected = select_presentation(original_bytes(receipt, INDEX_URL), receipt['retrieved_at'])
        self._authorized = {selected['pdf_url']}
        return selected
