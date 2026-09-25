"""Persist optional context cadence without promoting empty/error results to health."""
from __future__ import annotations

from dataclasses import asdict
import json

from .types import ProviderResult


def cached_context_result(provider, request, context, acquire):
    from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
    from shared_provider_cache import shared_fetch
    data = (context or {}).get('data') or {}
    key = json.dumps([provider.source, request.ticker,
                      *(data.get(field) for field in ('company_name', 'sector', 'industry',
                        'alternative_data_keywords', 'job_opening_keywords'))], ensure_ascii=False, sort_keys=True)
    ttl = max(0, int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(provider.source, 1800)))
    payload, meta = shared_fetch(
        'optional-context:v3:' + key, lambda: asdict(acquire(request, context)),
        freshness_seconds=ttl, use_cache=not request.options.force_refresh,
        result_ttl=lambda result: ttl if result.get('status') == 'success' else min(ttl, 600),
    )
    if not isinstance(payload, dict):
        return ProviderResult(source=provider.source, provider=provider.name, status='error', audit={
            'source':provider.source, 'provider':provider.name, 'status':'error', 'record_count':0,
            **meta, 'message':'補充來源暫未取得；不可由此推定沒有職缺或社群討論。'})
    result = ProviderResult(**payload)
    result.audit.update(meta)
    if isinstance(result.value, dict):
        result.value.update(meta)
    return result
