"""Persist optional context cadence without promoting empty/error results to health."""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import time

from .types import ProviderResult


def _kgi_origin(payload):
    value = payload.get('value') if isinstance(payload, dict) else None
    jobs = value.get('job_openings_official') if isinstance(value, dict) else None
    return (isinstance(jobs, dict)
            and jobs.get('source') == 'KGI Financial Holding official Workday careers')


def _kgi_live_remaining(payload):
    """Context assembly must not extend the earliest native receipt's 30 minutes."""
    try:
        jobs = payload['value']['job_openings_official']
        archive = jobs['source_record_archive']
        stamps = [r['fetched_at_epoch'] for r in
                  [archive['listing_receipt'], *archive['detail_receipts']]]
        if not stamps or any(type(v) not in (int, float) or not math.isfinite(v) for v in stamps):
            return 0
        original = min(stamps)
        if (original != jobs['fetched_at_epoch']
                or original != payload['audit']['fetched_at_epoch']):
            return 0
        age = time.time() - original
        return max(0, 1800 - age) if age >= 0 else 0
    except (KeyError, TypeError, ValueError, OverflowError):
        return 0


def cached_context_result(provider, request, context, acquire):
    from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
    from shared_provider_cache import shared_fetch
    data = (context or {}).get('data') or {}
    kgi_scope = provider.source == 'alternative_data' and request.ticker == '2883.TW'
    key = json.dumps([provider.source, request.ticker,
                      *(data.get(field) for field in ('company_name', 'sector', 'industry',
                        'alternative_data_keywords', 'job_opening_keywords')),
                      *([data.get(field) for field in ('ticker', 'company_identity', 'quote_type',
                                                       'quoteType', 'instrument_type')] if kgi_scope else [])],
                     ensure_ascii=False, sort_keys=True)
    ttl = max(0, int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(provider.source, 1800)))
    prefix = ('optional-context:philjobnet-v1:' if provider.source == 'alternative_data'
              and request.ticker == '9103.TW' else 'optional-context:v3:')
    if provider.source == 'alternative_data' and request.ticker == '9103.TW':
        prefix += provider.name + ':'
    if kgi_scope:
        prefix = 'optional-context:kgi-careers-v1:'
        ttl = min(ttl, 1800)
    def result_ttl(payload):
        if payload.get('status') != 'success':
            return min(ttl, 600)
        return min(ttl, _kgi_live_remaining(payload)) if kgi_scope and _kgi_origin(payload) else ttl

    def fetch_context(*, refresh=False):
        return shared_fetch(
            prefix + key, lambda: asdict(acquire(request, context)),
            freshness_seconds=ttl, use_cache=not request.options.force_refresh,
            result_ttl=result_ttl, force_refresh=refresh,
        )

    payload, meta = fetch_context()
    # Integer cache TTLs round up to at least one second. Recheck the original
    # lifetime on every read; refresh once under the same lock, respecting raw
    # provider guards. A retained error observation never initiates this path.
    if (kgi_scope and _kgi_origin(payload) and payload.get('status') == 'success'
            and _kgi_live_remaining(payload) <= 0 and meta.get('cache_hit')
            and not meta.get('stale') and not meta.get('error_kind')):
        payload, meta = fetch_context(refresh=True)
    if not isinstance(payload, dict):
        return ProviderResult(source=provider.source, provider=provider.name, status='error', audit={
            'source':provider.source, 'provider':provider.name, 'status':'error', 'record_count':0,
            **meta, 'message':'補充來源暫未取得；不可由此推定沒有職缺或社群討論。'})
    result = ProviderResult(**payload)
    philjobnet_origin = (provider.source == 'alternative_data' and request.ticker == '9103.TW'
        and (provider.name == 'PhilJobNet exact employer portal observation'
             or result.provider == 'PhilJobNet exact employer portal observation'
             or result.audit.get('provider') == 'PhilJobNet exact employer portal observation'
             or result.audit.get('coverage_status') == 'single_portal_numeric_observation'
             or isinstance(result.value,dict) and ('job_openings_philjobnet' in result.value
                 or 'philjobnet_employer_receipt' in result.value
                 or result.value.get('coverage_status') == 'single_portal_numeric_observation')))
    original_stamp = result.audit.get('fetched_at_epoch')
    original_cache_hit = bool(result.audit.get('cache_hit'))
    result.audit.update(meta)
    kgi_origin = kgi_scope and _kgi_origin(payload)
    if kgi_origin and result.status == 'success':
        from data_trust import source_record_count
        result.audit.update(fetched_at_epoch=original_stamp, cache_stored_at_epoch=meta.get('fetched_at_epoch'),
                            cache_hit=bool(meta.get('cache_hit')) or original_cache_hit)
        if result.audit['cache_hit']:
            result.audit.update(http_request_count=0, http_request_sent=False, event_kind='cache_hit')
        count = source_record_count('alternative_data', {**data, 'alternative_data': result.value})
        if (count <= 0 or count != result.audit.get('record_count')
                or _kgi_live_remaining(payload) <= 0 or meta.get('stale') or meta.get('error_kind')):
            return ProviderResult(source=provider.source, provider=provider.name, status='unavailable', audit={
                **result.audit, 'status':'unavailable', 'record_count':0, 'http_request_sent':False,
                'reason_code':'kgi_original_unverified', 'message':'官方職缺原件或目前雇主身分無法重新核對；數量未知。'})
    if philjobnet_origin:
        result.audit.update(fetched_at_epoch=original_stamp,cache_stored_at_epoch=meta.get('fetched_at_epoch'))
        if meta.get('cache_hit'):
            result.audit.update(http_request_count=0,http_request_sent=False,event_kind='cache_hit')
        from .market_sources.philjobnet_medtecs import verified_philjobnet_observation
        observation = result.value.get('job_openings_philjobnet') if isinstance(result.value,dict) else None
        if (not verified_philjobnet_observation(observation,
                {**data,'ticker':request.ticker},require_fresh=True)
                or result.source != 'alternative_data' or result.provider != 'PhilJobNet exact employer portal observation'
                or result.audit.get('source') != result.source or result.audit.get('provider') != result.provider
                or result.status != 'success' or result.audit.get('status') != 'success'
                or type(result.audit.get('record_count')) is not int or result.audit['record_count'] != 1
                or result.audit.get('fetched_at_epoch') != observation['fetched_at_epoch']):
            return ProviderResult(source=provider.source,provider=result.provider,status='error',audit={
                **result.audit,'status':'error','record_count':0,
                'reason_code':'philjobnet_original_unverified','message':'雇主入口原件無法重新核對；職缺數未知。'})
    if isinstance(result.value, dict):
        result.value.update(meta)
        if kgi_origin and result.status == 'success':
            result.value.update(fetched_at_epoch=original_stamp, cache_hit=result.audit['cache_hit'])
    return result
