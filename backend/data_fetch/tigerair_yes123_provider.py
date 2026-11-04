"""Officially linked exact-employer portal samples through the normal source path."""
from dataclasses import asdict
from hashlib import sha256
import json
import math
import time

from .types import ProviderResult
from .market_sources.tigerair_yes123_evidence import (TICKER, SHORT, PROVIDER,
    PAGE, ARTICLE, PROFILE, TTL, valid_context, verified_issuer, receipt_body,
    parse_mapping, parse_listing, parse_receipts, verified_job_count)

CANONICAL_PROVIDER = '104 & 1111 job openings'


def _failure(client=None, kind='issuer_original_unverified'):
    components = client.components if client else []
    count = client.http_request_count if client else 0
    sent = True if count else None if any(p.get('http_request_sent') is None for p in components) else False
    return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'unavailable', value={}, audit={
        'source': 'alternative_data', 'provider': CANONICAL_PROVIDER, 'actual_provider': PROVIDER,
        'status': 'unavailable', 'record_count': 0, 'event_kind': 'fetch' if components else 'local_block',
        'http_request_count': count, 'http_request_sent': sent,
        'cache_hit': bool(components) and all(p.get('cache_hit') is True for p in components),
        'error_kind': kind, 'component_statuses': {str(i): p for i, p in enumerate(components)},
        'message': '官網連出的精確雇主職缺樣本未完整核對；數量仍未知，不推論沒有職缺。'})


def _acquire(request, data):
    from .market_sources.official_company_legal_name import get_official_legal_name
    from .market_sources.tigerair_yes123_transport import TigerairCareersHttp
    deadline = time.monotonic() + 20
    client = None
    try:
        old = data.get('alternative_data')
        anchor = old.get('company_legal_name_evidence') if isinstance(old, dict) else None
        if not verified_issuer(anchor):
            anchor = get_official_legal_name(TICKER, SHORT)
        if not verified_issuer(anchor) or time.monotonic() >= deadline:
            return _failure(kind='issuer_original_unverified_or_deadline')
        client = TigerairCareersHttp(anchor, deadline=deadline,
                                   record_provider_sla=request.options.record_provider_sla)
        page = client.read(PAGE)
        article = client.read(ARTICLE)
        parse_mapping(receipt_body(page, PAGE, time.time()), receipt_body(article, ARTICLE, time.time()))
        listing = client.read(PROFILE)
        selected = parse_listing(receipt_body(listing, PROFILE, time.time()))['selected']
        receipts = [page, article, listing, *[client.read(row['url']) for row in selected]]
        jobs = parse_receipts(receipts, now=time.time())
        count = verified_job_count(jobs, data, anchor)
        if not count or time.monotonic() >= deadline:
            raise ValueError('portal_original_unverified_or_deadline')
        value = {'status': 'partial', 'coverage_status': 'partial',
            'company_legal_name_evidence': anchor, 'job_openings_yes123': jobs,
            'job_openings_104': [], 'job_openings_1111': [],
            'recent_recruitment_news': [], 'numeric_count_coverage': 0,
            'current_open_job_count_yes123': None, 'coverage_notes': [jobs['message']],
            'component_statuses': {'yes123': {'status': 'verified_company_posting_samples',
                'provider': PROVIDER, 'source_url': PROFILE, 'usable_count': count}}}
        audit = {'source': 'alternative_data', 'provider': CANONICAL_PROVIDER, 'actual_provider': PROVIDER,
            'status': 'success', 'event_kind': 'fetch', 'record_count': count, 'raw_count': count,
            'usable_count': count, 'coverage_status': 'partial', 'source_url': PROFILE,
            'response_sha256': jobs['response_sha256'], 'fetched_at_epoch': jobs['fetched_at_epoch'],
            'http_request_count': client.http_request_count, 'http_request_sent': client.http_request_count > 0,
            'cache_hit': all(p.get('cache_hit') is True for p in client.components), 'stale': False,
            'message': jobs['message'], 'component_statuses': {str(i): p for i, p in enumerate(client.components)}}
        return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'success', value=value, audit=audit)
    except (ValueError, OSError, UnicodeError, KeyError, TypeError, RuntimeError) as exc:
        return _failure(client, getattr(exc, 'error_kind', '') or type(exc).__name__)


def _remaining(payload):
    try:
        value = payload['value']; jobs = value['job_openings_yes123']
        stamps = [jobs['fetched_at_epoch'] + TTL,
                  value['company_legal_name_evidence']['fetched_at_epoch'] + 86400]
        if any(type(s) not in (int, float) or not math.isfinite(s) for s in stamps):
            return 0
        return max(0, min(stamps) - time.time())
    except (ValueError, TypeError, KeyError, OverflowError):
        return 0


def tigerair_context_result(request, context):
    from shared_provider_cache import shared_fetch, peek_fresh_shared
    from cache_store import peek_cache_json
    data = (context or {}).get('data') or {}
    if (request.ticker != TICKER or request.options.force_refresh or request.options.skip_optional_http
            or not valid_context(data)):
        return None
    # An existing normal observation, including an empty/error payload, keeps
    # its original cadence. A new namespace is not permission to bypass it.
    legacy_key = json.dumps(['alternative_data', TICKER,
        *[data.get(k) for k in ('company_name', 'sector', 'industry',
                               'alternative_data_keywords', 'job_opening_keywords')]],
        ensure_ascii=False, sort_keys=True)
    legacy, legacy_meta = peek_fresh_shared('optional-context:v3:' + legacy_key)
    if legacy is not None and legacy_meta.get('cache_hit'):
        return None
    legacy_owner = peek_cache_json('shared_provider:v1:' + sha256(
        ('optional-context:v3:' + legacy_key).encode()).hexdigest())
    if isinstance(legacy_owner, dict) and any(type(legacy_owner.get(k)) in (int, float)
            and math.isfinite(legacy_owner[k]) and legacy_owner[k] > time.time()
            for k in ('fresh_until_epoch', 'retry_after_epoch')):
        return None
    identity = data['company_identity']
    key = json.dumps([TICKER, data['company_name'],
        *[data.get(k) for k in ('ticker', 'stock_id', 'quote_type', 'quoteType', 'instrument_type')],
        *[identity.get(k) for k in ('ticker', 'official_name', 'legal_name', 'official_ubn',
                                   'stock_id', 'instrument_type', 'english_names')]], ensure_ascii=False)
    payload, meta = shared_fetch('optional-context:tigerair-yes123:v1:' + key,
        lambda: asdict(_acquire(request, data)), freshness_seconds=TTL, retention_seconds=TTL,
        error_retry_seconds=120, use_cache=True, lock_wait_seconds=1,
        result_ttl=lambda p: min(TTL, _remaining(p)) if p.get('status') == 'success' else 120)
    if not isinstance(payload, dict):
        return _failure(kind=meta.get('error_kind') or 'portal_context_unavailable')
    result = ProviderResult(**payload)
    if meta.get('cache_hit'):
        result.audit = {**result.audit, 'cache_hit': True, 'http_request_sent': False, 'http_request_count': 0}
    if (meta.get('error_kind') or meta.get('stale') or result.status == 'success' and (
            _remaining(payload) <= 0 or not verified_job_count(result.value.get('job_openings_yes123'), data,
                                            result.value.get('company_legal_name_evidence')))):
        return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'unavailable', value={}, audit={
            **result.audit, 'status': 'unavailable', 'record_count': 0, 'http_request_count': 0,
            'http_request_sent': False, 'error_kind': 'portal_original_unverified',
            'message': '雇主、職缺原件或原取得時間無法重新核對；數量未知。'})
    return result
