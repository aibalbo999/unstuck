"""Issuer-first THSRC career evidence with the original 30-minute raw lifetime."""
from dataclasses import asdict
import json
import time

from .types import ProviderResult
from .market_sources import thsrc_careers as source

CANONICAL_PROVIDER = '104 & 1111 job openings'


def _remaining(payload):
    try:
        value = payload['value']
        jobs = value['job_openings_official']
        if not source.verified_issuer(value['company_legal_name_evidence']): return 0
        if not source.verified_job_count(jobs, source.TICKER, source.LEGAL, source.UBN): return 0
        return max(0, min(jobs['fetched_at_epoch'] + 1800,
                          value['company_legal_name_evidence']['fetched_at_epoch'] + 86400) - time.time())
    except (KeyError, TypeError, ValueError, OverflowError): return 0


def _acquire(data):
    from .market_sources.official_company_legal_name import get_official_legal_name
    previous = data.get('alternative_data')
    anchor = previous.get('company_legal_name_evidence') if isinstance(previous, dict) else None
    if not source.verified_issuer(anchor): anchor = get_official_legal_name(source.TICKER, source.SHORT)
    audit = {'source': 'alternative_data', 'provider': CANONICAL_PROVIDER, 'actual_provider': source.PROVIDER,
             'status': 'unavailable', 'record_count': 0, 'http_request_count': 0, 'http_request_sent': False,
             'event_kind': 'local_block', 'cache_hit': False, 'stale': False}
    if not source.verified_issuer(anchor):
        return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'unavailable', value={},
                              audit={**audit, 'error_kind': 'issuer_original_unverified'})
    jobs = source.fetch_jobs()
    components = jobs.get('component_receipts') or []
    count = source.verified_job_count(jobs, source.TICKER, source.LEGAL, source.UBN)
    sent = jobs['http_request_count']
    audit.update(http_request_count=sent, http_request_sent=sent > 0,
                 cache_hit=bool(components) and all(r.get('cache_hit') is True for r in components),
                 event_kind='fetch', component_statuses={str(i): r for i, r in enumerate(components)})
    if not count:
        return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'unavailable', value={}, audit={
            **audit, 'error_kind': jobs.get('reason_code', 'official_career_unverified'),
            'message': '官方職缺原件或目前雇主身分未通過核對；保留其他來源與未知，不推論零職缺。'})
    value = {'status': 'partial', 'coverage_status': 'partial', 'company_legal_name_evidence': anchor,
             'job_openings_official': jobs, 'current_open_job_count_official': count,
             'job_openings_104': [], 'job_openings_1111': [], 'job_openings_taiwanjobs': None,
             'numeric_count_coverage': 0, 'recruitment_news_count': 0, 'recent_company_job_count_104': None,
             'current_open_job_count_taiwanjobs': None, 'recent_recruitment_news': [],
             'component_statuses': {'official': {'status': 'verified_company_postings', 'provider': source.PROVIDER,
                 'source_url': source.INDEX_URL, 'response_sha256': jobs['response_sha256'], 'usable_count': count}},
             'coverage_notes': [source.MESSAGE]}
    audit.update(status='success', record_count=count, raw_count=jobs['raw_count'], usable_count=count,
                 fetched_at_epoch=jobs['fetched_at_epoch'], source_url=source.INDEX_URL,
                 response_sha256=jobs['response_sha256'], coverage_status='partial', message=source.MESSAGE)
    return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'success', value=value, audit=audit)


def thsrc_context_result(request, context):
    from shared_provider_cache import shared_fetch
    data = (context or {}).get('data')
    if request.ticker != source.TICKER or request.options.force_refresh or not source.valid_context(data): return None
    identity = data['company_identity']
    key = json.dumps([source.TICKER, *[data.get(k) for k in (
        'company_name', 'ticker', 'stock_id', 'quote_type', 'quoteType', 'instrument_type')], identity],
        ensure_ascii=False, sort_keys=True)
    payload, meta = shared_fetch('optional-context:thsrc-careers:v1:' + key, lambda: asdict(_acquire(data)),
        freshness_seconds=1800, retention_seconds=1800, error_retry_seconds=300, use_cache=True,
        result_ttl=lambda p: min(1800, _remaining(p)) if p.get('status') == 'success' else 300, lock_wait_seconds=1)
    if not isinstance(payload, dict): return None
    result = ProviderResult(**payload)
    if meta.get('cache_hit'):
        result.audit = {**result.audit, 'cache_hit': True, 'http_request_sent': False, 'http_request_count': 0,
                        'event_kind': 'cache_hit'}
    if result.status == 'success' and (meta.get('stale') or meta.get('error_kind') or _remaining(payload) <= 0):
        return ProviderResult('alternative_data', CANONICAL_PROVIDER, 'unavailable', value={}, audit={
            **result.audit, 'status': 'unavailable', 'record_count': 0, 'error_kind': 'original_lifetime_expired'})
    return result
