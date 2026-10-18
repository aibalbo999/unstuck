"""One complete, bounded market notice original shared by all issuer queries."""
import base64
from datetime import datetime
from hashlib import sha256
import math
import re
import time
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from official_response_evidence import archive_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp
from .trading_notice_transport import ENDPOINT, MAX_BYTES


def query_params(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.twse.com.tw'
            or parsed.path != '/rwd/zh/announcement/notice' or parsed.fragment):
        raise ValueError('unverified market notice URL')
    values = parse_qs(parsed.query, keep_blank_values=True)
    if (set(values) != {'startDate', 'endDate', 'stockNo', 'selectType', 'querytype', 'sortKind', 'response'}
            or any(len(v) != 1 for v in values.values())):
        raise ValueError('unverified market notice query')
    params = {k: v[0] for k, v in values.items()}
    if any(params[k] != v for k, v in {'stockNo': '', 'selectType': '', 'querytype': '1',
                                      'sortKind': 'DATE', 'response': 'json'}.items()):
        raise ValueError('unverified market notice scope')
    days = []
    for key in ('startDate', 'endDate'):
        if not re.fullmatch(r'20\d{6}', params[key]):
            raise ValueError('invalid market notice date')
        days.append(datetime.strptime(params[key], '%Y%m%d').date())
    if not 0 <= (days[1] - days[0]).days <= 30:
        raise ValueError('market notice window exceeds limit')
    return params


def url_contract(url):
    try:
        query_params(url)
    except (ValueError, TypeError) as exc:
        raise SourceResponseError('transport_url_invalid') from exc
    return MAX_BYTES, {'application/json', 'text/json'}


class MarketNoticeHttp(IssuerNewsHttp):
    route_contract = staticmethod(url_contract)

    def get(self, url):
        raw = super().get(url)
        component = self.components[-1]
        stamp = component['fetched_at_epoch']
        # shared_fetch's public metadata omits a potentially shorter expiry.
        # Read only the same original; never renew or replace its cache row.
        from cache_store import get_cache_json
        key = 'shared_provider:v1:' + sha256(('issuer-news-raw:v1:' + url).encode()).hexdigest()
        try:
            row = get_cache_json(key)
        except Exception:
            row = None
        until = stamp + 1800
        if row is not None:
            value = row.get('value') if isinstance(row, dict) else None
            expiry = row.get('fresh_until_epoch') if isinstance(row, dict) else None
            if (not isinstance(value, dict) or row.get('error_kind')
                    or value.get('url') != url or value.get('sha256') != sha256(raw).hexdigest()
                    or row.get('fetched_at_epoch') != stamp
                    or type(expiry) not in (int, float) or not math.isfinite(expiry)
                    or not stamp < expiry):
                raise SourceResponseError('cache_receipt_invalid')
            until = min(until, expiry)
        elif component.get('cache_hit'):
            raise SourceResponseError('cache_receipt_invalid')
        component['fresh_until_epoch'] = until
        if time.time() >= until or time.monotonic() >= self.deadline:
            raise SourceResponseError('stale_receipt' if time.time() >= until else 'timeout')
        return raw

    def _download(self, url, diagnostic):
        from .twse_market_trading_notices import parse_market_rows
        try:
            value = super()._download(url, diagnostic)
        except SourceResponseError as exc:
            diagnostic.update(exc.diagnostic)
            raise
        raw = base64.b64decode(value['body_b64'])
        diagnostic.update(http_status=200, raw_response_receipt=archive_response(
            raw, source_url=url, retrieved_at=time.time(), http_status=200))
        try:
            parse_market_rows(raw, url, datetime.now(ZoneInfo('Asia/Taipei')))
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            diagnostic['error_kind'] = 'parse_error'
            raise SourceResponseError('parse_error', status_code=200) from exc
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout', status_code=200)
        return value
