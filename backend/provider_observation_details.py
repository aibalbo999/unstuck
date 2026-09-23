"""Bounded structured source evidence; never persist credentials or response bodies."""
from __future__ import annotations

import math
from provider_correlation import correlation_metadata

_TEXT = {'outcome', 'error_kind', 'parser_version', 'response_sha256', 'actual_provider',
         'coverage_status', 'fallback_reason', 'market', 'instrument_type', 'rate_kind'}
_BOOL = {'http_request_sent', 'cache_hit', 'stale', 'mapping_verified'}
_NUMBER = {'http_status', 'retry_at', 'fetched_at_epoch', 'response_bytes'}


def observation_details(entry: dict) -> dict:
    result = correlation_metadata(entry)
    for key in _TEXT:
        value = entry.get(key)
        if isinstance(value, str):
            result[key] = value[:160]
    for key in _BOOL:
        if isinstance(entry.get(key), bool):
            result[key] = entry[key]
    for key in _NUMBER:
        value = entry.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[key] = value
    for key in ('coverage', 'component_statuses'):
        value = entry.get(key)
        if isinstance(value, dict):
            result[key] = {
                str(name)[:80]: ({str(k): v[:160] if isinstance(v, str) else v for k, v in item.items()
                                 if k in {'status', 'as_of', 'provider', 'reason_code', 'series_id', 'error_kind',
                                          'fetched_at_epoch', 'stale', 'cache_hit', 'retry_after_epoch',
                                          'observation_status', 'observation_age_days'}
                                 and isinstance(v, (str, bool, int, float))
                                 and (not isinstance(v, (int, float)) or math.isfinite(v))}
                                if isinstance(item, dict) else item[:80])
                for name, item in list(value.items())[:20] if isinstance(item, (dict, str))
            }
    return result
