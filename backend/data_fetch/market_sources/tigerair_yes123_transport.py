"""Bounded anonymous reads, gated by actual published actions and live issuer."""
from contextlib import suppress
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
import sqlite3
import time
from urllib.parse import urlsplit

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import (SourceResponseError, cooldown_state,
    observe_http_response, remember_failure, scope_key)
from shared_provider_cache import shared_fetch
from .construction_cohort_transport import _headers
from .tigerair_yes123_evidence import (RAW_PREFIX, allowed_url, native_receipt,
    receipt_body, verified_issuer, TICKER, PROVIDER, PAGE, ARTICLE, PROFILE,
    MAX_BYTES, MAX_POSTINGS, TTL, parse_mapping, parse_listing)


class TigerairCareersHttp:
    def __init__(self, issuer, *, deadline=None, record_provider_sla=False):
        if not verified_issuer(issuer):
            raise SourceResponseError('issuer_original_unverified')
        self.issuer = deepcopy(issuer)
        self.deadline = time.monotonic() + 20 if deadline is None else deadline
        self.record_provider_sla = record_provider_sla is True
        self.http_request_count = 0
        self.components = []
        self.seen = set()
        self.staged = {}

    def _emit(self, diagnostic, receipt=None):
        if not self.record_provider_sla or not diagnostic.get('client_process_started'):
            return
        from provider_correlation import current_correlation, current_source_identity
        from provider_sla import record_source_audit_entries
        context = current_correlation()
        if (context.get('ticker') != TICKER or not context.get('fetch_id') or not context.get('operation_id')
                or current_source_identity() != ('alternative_data', '104 & 1111 job openings')):
            return
        component = deepcopy(diagnostic)
        if receipt is not None:
            component['original_receipt'] = {**receipt['raw_receipt'],
                'http_status_observed': True, 'response_complete': True,
                'request_method': 'GET', 'cache_hit': False}
        with suppress(sqlite3.Error):
            record_source_audit_entries([{**context, 'source': 'alternative_data',
                'provider': PROVIDER + ' native HTTP', 'status': 'success' if receipt else 'error',
                'event_kind': 'http_transport_receipt', 'selection_policy': 'transport-receipt-only:v1',
                'record_count': 0, 'http_request_sent': diagnostic.get('http_request_sent'),
                'http_status_observed': diagnostic.get('http_status_observed'),
                'response_complete': bool(receipt), 'http_status': diagnostic.get('http_status'),
                'response_bytes': diagnostic.get('response_bytes'),
                'response_sha256': diagnostic.get('response_sha256'),
                'component_statuses': [component],
                'message': 'Public portal transport only; issuer, dates, complete originals and job qualification are separate.'}])

    def _consume(self, url, parts, rc, error, diagnostic):
        status, headers = _headers(parts['headers'])
        try:
            meta = json.loads(parts['metadata'])
        except (ValueError, UnicodeError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        if status is None and type(meta.get('http_code')) is int and 200 <= meta['http_code'] <= 599:
            status = meta['http_code']
        observed = (parts.get('process_started') is True and type(meta.get('http_code')) is int
            and status == meta['http_code'] and type(status) is int and 200 <= status <= 599
            and meta.get('url_effective') == url and type(meta.get('ssl_verify_result')) is int
            and meta['ssl_verify_result'] == 0 and type(meta.get('proxy_used')) is int and meta['proxy_used'] == 0)
        started = parts.get('process_started') is True
        raw = parts['body']
        diagnostic.update(client_process_started=started,
            http_request_sent=True if observed else None if started else False,
            http_request_count=int(observed), http_status=status,
            http_status_observed=status is not None, response_complete=False,
            response_bytes=len(raw), response_sha256=sha256(raw).hexdigest(), request_method='GET')
        self.http_request_count += int(observed)
        response = httpx.Response(status, headers=headers, request=httpx.Request('GET', url)) if status else None
        if response is not None:
            observe_http_response(response)

        def fail(kind):
            diagnostic['error_kind'] = kind
            self._emit(diagnostic)
            exc = SourceResponseError(kind, status_code=status)
            exc.diagnostic.update(http_status_observed=status is not None, response_complete=False,
                                  response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
            if response is not None:
                exc.response = response
            if status in {401, 402, 403, 429} or status and status >= 500:
                remember_failure(scope_key(PROVIDER, endpoint=urlsplit(url).hostname), exc)
            raise exc

        if status is not None and status != 200:
            fail({401: 'authentication', 402: 'payment_required', 403: 'access_denied',
                  429: 'rate_limited'}.get(status, 'server_error' if status >= 500 else 'http_error'))
        if error or rc:
            fail(error or ('timeout' if rc == 28 else 'response_too_large' if rc == 63 else 'transport_error'))
        if (not observed or type(meta.get('num_redirects')) is not int or meta['num_redirects'] != 0):
            fail('transport_metadata_invalid')
        mime = headers.get('content-type', '').lower().split(';')
        expected_mime = 'application/json' if url == ARTICLE else 'text/html'
        if (mime[0].strip() != expected_mime
                or url != ARTICLE and 'charset=utf-8' not in {s.strip().replace(' ', '') for s in mime[1:]}):
            fail('unexpected_content_type')
        if headers.get('content-encoding', 'identity').lower() not in {'', 'identity'}:
            fail('unsupported_content_encoding')
        size = meta.get('size_download')
        if not 0 < len(raw) <= MAX_BYTES or type(size) not in (int, float) or not math.isfinite(size) or size != len(raw):
            fail('transport_body_incomplete')
        if time.monotonic() >= self.deadline:
            fail('timeout')
        receipt = native_receipt(raw, url, time.time(), {'http_status': 200,
            'http_status_observed': True, 'response_complete': True, 'http_request_sent': True,
            'return_code': 0, 'ssl_verify_result': 0, 'proxy_used': 0, 'num_redirects': 0, 'response_bytes': len(raw)})
        diagnostic.update(response_complete=True)
        self._emit(diagnostic, receipt)
        return receipt

    def _download(self, url, diagnostic):
        from cache_store import get_cache_json
        allowed_url(url)
        def block(kind):
            diagnostic.update(error_kind=kind, http_status=None, http_status_observed=False,
                response_complete=False, http_request_sent=False, http_request_count=0)
            exc = SourceResponseError(kind)
            exc.diagnostic.update(http_status_observed=False, response_complete=False)
            raise exc
        if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
            block('test_network_disabled')
        if proxy_url_for_request(url, PROVIDER) or any(os.getenv(k) for k in
                ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')):
            block('proxy_configuration_unsupported')
        host = urlsplit(url).hostname
        if any(cooldown_state(scope_key(p, endpoint=host)) for p in (PROVIDER, 'Verified issuer news')):
            block('cooldown')
        # Do not use a new namespace to bypass a previously retained raw source.
        legacy = get_cache_json('shared_provider:v1:' + sha256(('issuer-news-raw:v1:' + url).encode()).hexdigest())
        if isinstance(legacy, dict) and any(type(legacy.get(k)) in (int, float)
                and math.isfinite(legacy[k]) and legacy[k] > time.time()
                for k in ('fresh_until_epoch', 'retry_after_epoch')):
            block('legacy_raw_cache_still_live')
        remaining = min(5., self.deadline - time.monotonic())
        if remaining <= 0:
            block('timeout')
        argv = ['/usr/bin/curl', '--disable', '--silent', '--max-time', str(remaining),
            '--connect-timeout', str(min(2., remaining)), '--max-filesize', str(MAX_BYTES),
            '--proto', '=https', '--max-redirs', '0', '--retry', '0',
            '--dump-header', '/dev/fd/{HEADER_FD}', '--write-out', '%{stderr}%{json}', url]
        parts, rc, error = collect_capped_process(argv, min(self.deadline, time.monotonic() + remaining),
                                                 body_limit=MAX_BYTES, headers=True)
        return self._consume(url, parts, rc, error, diagnostic)

    def read(self, url):
        allowed_url(url)
        if not verified_issuer(self.issuer) or time.monotonic() >= self.deadline:
            raise SourceResponseError('issuer_expired_or_deadline')
        if url in self.seen or len(self.seen) >= 3 + MAX_POSTINGS:
            raise SourceResponseError('portal_request_set_invalid')
        # A caller cannot authorize detail URLs by fabricating a candidate list.
        if url == ARTICLE and PAGE not in self.staged:
            raise SourceResponseError('official_page_required')
        if url == PROFILE or url not in (PAGE, ARTICLE, PROFILE):
            if not all(u in self.staged for u in (PAGE, ARTICLE)):
                raise SourceResponseError('official_mapping_required')
            parse_mapping(receipt_body(self.staged[PAGE], PAGE, time.time()),
                          receipt_body(self.staged[ARTICLE], ARTICLE, time.time()))
        if url not in (PAGE, ARTICLE, PROFILE):
            if PROFILE not in self.staged:
                raise SourceResponseError('published_profile_required')
            selected = parse_listing(receipt_body(self.staged[PROFILE], PROFILE, time.time()))['selected']
            if url not in {r['url'] for r in selected}:
                raise SourceResponseError('posting_action_not_published')
        self.seen.add(url)
        diagnostic = {'url': url, 'provider': PROVIDER, 'http_request_sent': False,
                      'http_request_count': 0, 'http_status_observed': False, 'cache_hit': False}
        self.components.append(diagnostic)
        receipt, meta = shared_fetch(RAW_PREFIX + url, lambda: self._download(url, diagnostic),
            freshness_seconds=TTL, retention_seconds=TTL, error_retry_seconds=120,
            use_cache=True, lock_wait_seconds=1)
        diagnostic.update(cache_hit=bool(meta.get('cache_hit')), fetched_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('error_kind') or meta.get('stale') or not isinstance(receipt, dict):
            kind = diagnostic.get('error_kind') or meta.get('error_kind') or 'portal_receipt_unavailable'
            exc = SourceResponseError(kind, status_code=diagnostic.get('http_status'))
            exc.diagnostic.update(http_status_observed=diagnostic.get('http_status_observed') is True,
                                  response_complete=False)
            raise exc
        receipt_body(receipt, url, time.time())
        if time.monotonic() >= self.deadline or not verified_issuer(self.issuer):
            raise SourceResponseError('issuer_expired_or_deadline')
        diagnostic['original_receipt'] = {**receipt['raw_receipt'],
            'http_status_observed': True, 'response_complete': True, 'cache_hit': False, 'request_method': 'GET'}
        self.staged[url] = deepcopy(receipt)
        return receipt
