"""Capped official CSV GETs; qualified native originals retain their first TTL."""
import base64
from hashlib import sha256
import math
import time

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from shared_provider_cache import shared_fetch
from .issuer_news_transport import IssuerNewsHttp
from .official_monthly_revenue import MAX_BYTES, URLS, _today, parse_monthly_snapshot


def url_contract(url):
    if url not in URLS.values():
        raise SourceResponseError('transport_url_invalid')
    return MAX_BYTES, {'text/csv', 'application/csv'}


class MonthlyRevenueHttp(IssuerNewsHttp):
    # Keep the existing exact-host cooldown, native TLS, 5s/connect2 bounds,
    # no credentials, redirects, proxies or retries. Do not call its news cache.
    route_contract = staticmethod(url_contract)

    def _download(self, url, diagnostic):
        try:
            value = super()._download(url, diagnostic)
        except SourceResponseError as exc:
            diagnostic.update(http_status=exc.status_code, error_kind=exc.error_kind)
            raise
        raw = base64.b64decode(value['body_b64'], validate=True)
        receipt = archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200)
        diagnostic.update(http_status=200, original_receipt=receipt)
        try:
            parse_monthly_snapshot(raw, url, _today())
            if receipt.get('status') != 'archived' or read_response(receipt) != raw:
                raise ValueError('monthly_original_unverified')
        except (ValueError, TypeError, KeyError, OSError, EOFError) as exc:
            diagnostic['error_kind'] = 'parse_error'
            raise SourceResponseError('parse_error', status_code=200) from exc
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout', status_code=200)
        return {**value, 'original_receipt': receipt}

    def get(self, url):
        url_contract(url)
        diagnostic = {'url': url, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        value, meta = shared_fetch('official-monthly-raw:v1:' + url,
                                  lambda: self._download(url, diagnostic),
                                  freshness_seconds=1800, retention_seconds=1800,
                                  error_retry_seconds=120, lock_wait_seconds=1)
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')), fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale'):
            raise SourceResponseError(diagnostic.get('error_kind') or meta.get('error_kind') or 'stale_receipt')
        try:
            stamp = meta['fetched_at_epoch']
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= time.time() - stamp < 1800:
                raise ValueError
            if not isinstance(value, dict) or value.get('url') != url:
                raise ValueError
            encoded = value['body_b64']
            if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
                raise ValueError
            raw = base64.b64decode(encoded, validate=True)
            receipt = value['original_receipt']
            original = receipt['retrieved_at']
            native_fields = {'status', 'source_url', 'retrieved_at', 'http_status',
                             'raw_response_sha256', 'raw_response_path', 'raw_response_bytes',
                             'evidence_kind', 'historical_point_in_time_verified', 'finality_guaranteed'}
            if (not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != value.get('sha256')
                    or set(receipt) != native_fields
                    or receipt.get('historical_point_in_time_verified') is not False
                    or receipt.get('finality_guaranteed') is not False
                    or receipt.get('source_url') != url or receipt.get('http_status') != 200
                    or receipt.get('status') != 'archived' or receipt.get('evidence_kind') != 'raw_http_response_bytes'
                    or type(receipt.get('raw_response_bytes')) is not int or receipt['raw_response_bytes'] != len(raw)
                    or type(original) not in (int, float) or not math.isfinite(original)
                    or not 0 <= stamp - original <= 10 or not 0 <= time.time() - original < 1800
                    or read_response(receipt) != raw):
                raise ValueError
        except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
            raise SourceResponseError('cache_receipt_invalid') from None
        diagnostic.update(http_status=200, original_receipt=receipt)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw, receipt
