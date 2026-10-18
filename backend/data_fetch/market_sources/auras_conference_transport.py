"""Ordinary anonymous Auras originals under the reviewed conference transport."""
import re
from search_provider_runtime import SourceResponseError
from .tcfhc_conference_transport import ConferenceHttp, original_bytes as _original_bytes

MASTER = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
INDEX = 'https://www.auras.com.tw/CmsApi/api/Unit/getUnitContentAsync?UnitId=46&Keyword=&IsFront=true&IsList=false&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true'
PROVIDER = 'Auras official conference presentation'
PDF_ROUTE = re.compile(r'https://www\.auras\.com\.tw/CMSFS/UnitContents/AnnexChinese/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.pdf')


def pdf_url(value):
    return isinstance(value, str) and PDF_ROUTE.fullmatch(value) is not None


def contract(url):
    if url == MASTER:
        return 2_500_000, {'application/json', 'text/json'}
    if url == INDEX:
        return 200_000, {'application/json', 'text/json'}
    if pdf_url(url):
        return 3_000_000, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


class AurasConferenceHttp(ConferenceHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'auras-conference-raw:v1:'
    admission_prefix = 'auras-conference-admission:v1:'

    def request_timeout_seconds(self, url):
        # A live official PDF request timed out at the prior eight-second cap.
        # Give this single download up to twelve seconds while the enclosing
        # conference workflow remains bounded by its existing twenty-second deadline.
        return 12. if pdf_url(url) else super().request_timeout_seconds(url)


def original_bytes(receipt, url, *, max_age=86400):
    return _original_bytes(receipt, url, max_age=max_age, url_contract=contract)
