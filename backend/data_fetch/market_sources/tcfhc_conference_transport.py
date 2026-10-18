"""Bounded anonymous original-byte transport for published TCFHC QA documents."""
import base64
from hashlib import sha256
import math
import re
import time
from uuid import uuid4
from urllib.parse import parse_qsl, urlsplit

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key
from shared_provider_cache import shared_fetch
from .issuer_news_transport import IssuerNewsHttp, PROVIDER as HTTP_PROVIDER

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
HOST = 'https://www.tcfhc.com.tw'
ROOT = HOST + '/investors-relations/event/'
PROVIDER = 'TCFHC official investor QA summary'
RAW_TTL = 1800
RECEIPT_FIELDS = {'status', 'source_url', 'retrieved_at', 'http_status', 'raw_response_sha256',
                  'raw_response_path', 'raw_response_bytes', 'evidence_kind',
                  'historical_point_in_time_verified', 'finality_guaranteed',
                  'http_status_observed', 'request_method', 'response_complete', 'cache_hit'}


def route_kind(url):
    if url == MASTER_URL:
        return 'master'
    if not isinstance(url, str):
        return None
    if re.fullmatch(re.escape(ROOT) + r'20\d{2}year', url):
        return 'index'
    if re.fullmatch(re.escape(ROOT) + r'(20\d{2})year/\1q[1-4]', url):
        return 'event'
    u = urlsplit(url)
    if (u.scheme != 'https' or u.netloc != 'www.tcfhc.com.tw' or u.fragment
            or not re.fullmatch(r'/-/media/files/tcfhc/investors-relations/event/(20\d{2})year/\1q[1-4]question\.pdf', u.path)):
        return None
    try:
        pairs = parse_qsl(u.query, strict_parsing=True)
    except ValueError:
        return None
    if (len(pairs) == 2 and dict(pairs).get('sc_lang') == 'zh-tw'
            and re.fullmatch(r'[A-F0-9]{16,64}', dict(pairs).get('hash', ''))):
        return 'qa'
    return None


def contract(url):
    kind = route_kind(url)
    if kind == 'master':
        return 2_500_000, {'text/csv', 'application/csv', 'application/octet-stream'}
    if kind in {'index', 'event'}:
        return 500_000, {'text/html', 'application/xhtml+xml'}
    if kind == 'qa':
        return 2_000_000, {'application/pdf', 'application/octet-stream'}
    raise SourceResponseError('transport_url_invalid')


def valid_epoch(value, max_age):
    try:
        return (type(value) in (int, float) and math.isfinite(value)
                and 0 <= time.time() - value < max_age)
    except (OverflowError, ValueError):
        return False


def original_bytes(receipt, url, *, max_age=86400, url_contract=contract):
    limit, _ = url_contract(url)
    if (not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS or receipt.get('status') != 'archived'
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or receipt.get('source_url') != url
            or not valid_epoch(receipt.get('retrieved_at'), max_age)
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != 200
            or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('http_status_observed') is not True
            or receipt.get('request_method') != 'GET' or receipt.get('response_complete') is not True
            or type(receipt.get('cache_hit')) is not bool
            or any(k in receipt for k in ('cache_source', 'source_payload_sha256', 'source_payload_bytes'))):
        raise ValueError('TCFHC original receipt unverified')
    raw = read_response(receipt)
    if type(receipt.get('raw_response_bytes')) is not int or not 0 < len(raw) <= limit or len(raw) != receipt['raw_response_bytes']:
        raise ValueError('TCFHC original size unverified')
    return raw


class ConferenceHttp(IssuerNewsHttp):
    route_contract = staticmethod(contract)
    raw_cache_prefix = 'tcfhc-qa-raw:v1:'
    admission_prefix = 'tcfhc-qa-admission:v1:'

    def request_timeout_seconds(self, url):
        # The shared official issuer roster is a 2.5 MB CSV and is the first
        # request for both conference QA and issuer-news lookups. Give this
        # single shared fetch a wider response window while preserving the
        # normal operation deadline and shorter company-page limits.
        return 8. if url == MASTER_URL else super().request_timeout_seconds(url)

    def connect_timeout_seconds(self, url):
        return 3. if url == MASTER_URL else super().connect_timeout_seconds(url)

    def __init__(self, deadline, *, force_refresh=False, use_cache=True):
        super().__init__(deadline)
        # Explicit uncached acquisition still uses the shared single-flight
        # lock and publishes the new ordinary observation for later readers.
        self.force_refresh = force_refresh or not use_cache

    def _retry_guard(self, url):
        from cache_store import get_cache_json
        try:
            key = 'shared_provider:v1:' + sha256((self.raw_cache_prefix + url).encode()).hexdigest()
            row = get_cache_json(key)
            if isinstance(row, dict) and row.get('error_kind'):
                until = row.get('retry_after_epoch')
                if type(until) not in (int, float) or not math.isfinite(until) or until < 0:
                    raise ValueError('invalid retry state')
                if until > time.time():
                    raise SourceResponseError('cooldown')
            admission = get_cache_json(self._admission_key(url))
            if admission is not None:
                until = admission.get('retry_at') if isinstance(admission, dict) else None
                if type(until) not in (int, float) or not math.isfinite(until) or until < 0:
                    raise ValueError('invalid admission state')
                if until > time.time():
                    raise SourceResponseError('cooldown')
        except SourceResponseError:
            raise
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc

    @classmethod
    def _admission_key(cls, url):
        return cls.admission_prefix + sha256(url.encode()).hexdigest()

    def native_status(self, url):
        return 200

    def download_original(self, url, diagnostic):
        return super()._download(url, diagnostic)

    def archive_original(self, raw, url, value):
        return archive_response(raw, source_url=url, retrieved_at=value['fetched_at_epoch'])

    def read_original(self, receipt, url, *, max_age):
        return original_bytes(receipt, url, max_age=max_age, url_contract=self.route_contract)

    def _download(self, url, diagnostic):
        # The shared HTTP helper tolerates unavailable guard storage. This
        # source must not issue another request when its cooldown is unknown.
        self._retry_guard(url)
        from cache_store import get_cache_json
        try:
            state = get_cache_json(scope_key(HTTP_PROVIDER, endpoint=urlsplit(url).hostname))
            if state is not None:
                until = state.get('retry_at') if isinstance(state, dict) else None
                if type(until) not in (int, float) or not math.isfinite(until) or until < 0:
                    raise ValueError('invalid cooldown state')
                if until > time.time():
                    raise SourceResponseError('cooldown')
        except SourceResponseError:
            raise
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        from cache_store import set_cache_json
        key = self._admission_key(url)
        marker = {'token': uuid4().hex, 'retry_at': time.time() + 120}
        try:
            # Reserve a short failure cooldown before HTTP. A read-only store
            # must not silently permit requests whose failures cannot be saved.
            set_cache_json(key, marker, ttl_seconds=120)
            if get_cache_json(key) != marker:
                raise SourceResponseError('lease_lost')
        except SourceResponseError:
            raise
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        value = self.download_original(url, diagnostic)
        try:
            if get_cache_json(key) == marker:
                set_cache_json(key, {**marker, 'retry_at': 0}, ttl_seconds=1)
        except Exception:
            # Keep the reservation on cleanup failure; the completed original
            # remains valid, but another native request must wait.
            diagnostic['admission_release_failed'] = True
        # The base only returns after verifying the original native status,
        # URL, complete process, size, MIME and lack of redirection.
        return {**value, 'http_status': self.native_status(url), 'response_complete': True,
                'request_method': 'GET', 'http_status_observed': True, 'fetched_at_epoch': time.time()}

    def get_receipt(self, url):
        limit, _ = self.route_contract(url)
        diagnostic = {'url': url, 'http_request_sent': False}
        self.components.append(diagnostic)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        if self.force_refresh:
            # Preserve an active error row without extending its retry time.
            self._retry_guard(url)

        def remaining_ttl(value):
            stamp = value.get('fetched_at_epoch') if isinstance(value, dict) else None
            if not valid_epoch(stamp, RAW_TTL):
                raise SourceResponseError('original_expired')
            remaining = math.floor(stamp + RAW_TTL - time.time())
            if remaining < 1:
                raise SourceResponseError('original_expired')
            return remaining

        failure = []

        def collect():
            try:
                return self._download(url, diagnostic)
            except SourceResponseError as exc:
                failure.append(exc)
                raise

        value, meta = shared_fetch(self.raw_cache_prefix + url, collect,
                                  freshness_seconds=RAW_TTL, retention_seconds=RAW_TTL,
                                  result_ttl=remaining_ttl, error_retry_seconds=120,
                                  force_refresh=self.force_refresh,
                                  lock_wait_seconds=min(1., max(0., self.deadline - time.monotonic())))
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')), fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale'):
            if failure:
                raise failure[0]
            kind = meta.get('error_kind') or 'stale_receipt'
            # Persisted shared failures retain only the exception class; do
            # not invent the original HTTP cause during the retry cooldown.
            raise SourceResponseError('cooldown' if kind == 'SourceResponseError' else kind)
        if (not isinstance(value, dict) or value.get('url') != url
                or not valid_epoch(value.get('fetched_at_epoch'), RAW_TTL)
                or type(value.get('http_status')) is not int or value['http_status'] != self.native_status(url)
                or value.get('response_complete') is not True or value.get('http_status_observed') is not True
                or value.get('request_method') != 'GET'):
            raise SourceResponseError('cache_receipt_invalid')
        encoded = value.get('body_b64')
        if not isinstance(encoded, str) or len(encoded) > (limit + 2) // 3 * 4:
            raise SourceResponseError('cache_receipt_invalid')
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= limit or sha256(raw).hexdigest() != value.get('sha256'):
            raise SourceResponseError('cache_receipt_invalid')
        receipt = self.archive_original(raw, url, value)
        receipt.update(http_status_observed=True, request_method='GET', response_complete=True,
                       cache_hit=bool(meta.get('cache_hit')))
        if self.read_original(receipt, url, max_age=RAW_TTL) != raw:
            raise SourceResponseError('original_unverified')
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        diagnostic.update(fetched_at_epoch=value['fetched_at_epoch'], original_receipt=receipt,
                          http_status=self.native_status(url), original_http_status_observed=True)
        return raw, receipt
