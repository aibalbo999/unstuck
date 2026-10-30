"""Bounded structured source evidence; never persist credentials or response bodies."""
from __future__ import annotations

import math
import re
from urllib.parse import urlsplit
from provider_correlation import correlation_metadata

_TEXT = {'outcome', 'error_kind', 'acquisition_count_policy', 'parser_version', 'response_sha256', 'actual_provider',
         'coverage_status', 'quality_status', 'retrieval_status', 'qualified_result_status', 'selection_policy', 'selection_cutoff', 'fallback_reason', 'market', 'instrument_type', 'rate_kind'}
_BOOL = {'http_request_sent', 'cache_hit', 'stale', 'mapping_verified', 'progress_resume_possible',
         'body_cache_hit', 'result_quality_satisfied'}
_NUMBER = {'acquisition_record_count', 'http_status', 'retry_at', 'fetched_at_epoch', 'response_bytes', 'raw_count', 'usable_count', 'rejected_count',
           'http_request_count', 'progress_missing_count', 'progress_fresh_until_epoch',
           'progress_remaining_seconds', 'detail_cache_hit_count', 'detail_new_body_count', 'body_fetched_at_epoch',
           'result_publisher_count'}


_VERIFICATION = {
    'document_error_kind': {'invalid_pdf','encrypted_pdf','page_limit','character_limit',
        'empty_document','parser_unavailable','parser_version_mismatch','parser_warning',
        'stream_limit','resource_limits_unavailable','timeout','invalid_input','invalid_timeout',
        'memory_limit','memory_accounting_unavailable','worker_failed','worker_diagnostic',
        'worker_cleanup_failed','invalid_worker_result','stdout_limit','stderr_limit'},
    'verification_status': {'verified','rejected'},
    'verification_stage': {'context','proof','master_original','master_identity','index_request',
        'index_original','index_selection','index_current','material_request','material_original',
        'native_material','projection','receipt_age','index_handoff','material_handoff',
        'master_handoff','deadline','freshness','complete'},
    'verification_reason': {'none','unsupported_context','invalid_proof','request_mismatch',
        'selection_mismatch','projection_mismatch','expired','parser_timeout','parser_warning',
        'document_restricted','document_limit','document_rejected','source_timeout',
        'source_rejected','original_unreadable','invalid_structure','validation_error','memory_accounting_unavailable'},
}


def _announcement_attempts(value):
    """Keep typed failure evidence, without queries, headers or original bodies."""
    endpoints = {
        ('wwwc.twse.com.tw', '/rwd/zh/IIH/company/events'),
        ('mopsov.twse.com.tw', '/mops/web/ezsearch_query'),
        ('mopsov.twse.com.tw', '/mops/web/ajax_t05sr01_1'),
        ('mops.twse.com.tw', '/mops/api/t05st01'),
    }
    out = []
    for item in value[:64]:
        if not isinstance(item, dict):
            continue
        row = {}
        url = item.get('url')
        if isinstance(url, str) and len(url) <= 4096:
            try:
                parsed = urlsplit(url)
                if parsed.scheme == 'https' and (parsed.netloc, parsed.path) in endpoints:
                    row['url'] = f'https://{parsed.netloc}{parsed.path}'
            except ValueError:
                pass
        for key, allowed in (('method', {'GET', 'POST'}), ('status', {'success', 'error', 'cache_hit'})):
            if isinstance(item.get(key), str) and item[key] in allowed:
                row[key] = item[key]
        kind = item.get('error_kind')
        if isinstance(kind, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,79}', kind):
            row['error_kind'] = kind
        for key in ('request_fingerprint', 'response_sha256'):
            if isinstance(item.get(key), str) and re.fullmatch(r'[0-9a-f]{64}', item[key]):
                row[key] = item[key]
        for key in ('http_request_sent', 'response_complete', 'http_status_observed'):
            if type(item.get(key)) is bool:
                row[key] = item[key]
        for key in ('elapsed_seconds', 'remaining_seconds', 'response_bytes', 'http_request_count', 'http_status'):
            number = item.get(key)
            if type(number) not in (int, float):
                continue
            try:
                valid = math.isfinite(number) and 0 <= number <= 100_000_000
            except OverflowError:
                valid = False
            if key == 'http_status':
                valid = type(number) is int and 100 <= number <= 599
            elif key == 'http_request_count':
                valid = type(number) is int and number in (0, 1)
            if valid:
                row[key] = number
        out.append(row)
    return out


def observation_details(entry: dict) -> dict:
    result = correlation_metadata(entry)
    for key,allowed in _VERIFICATION.items():
        value=entry.get(key)
        if isinstance(value,str) and value in allowed:
            result[key]=value
    for key in _TEXT:
        value = entry.get(key)
        if isinstance(value, str):
            result[key] = value[:160]
    for key in _BOOL:
        if isinstance(entry.get(key), bool):
            result[key] = entry[key]
    for key in _NUMBER:
        value = entry.get(key)
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if valid:
            result[key] = value
    reasons = entry.get('rejected_reason_counts')
    if (entry.get('provider') == 'TWSE company announcement history'
            and isinstance(entry.get('request_observations'), list)):
        result['request_observations'] = _announcement_attempts(entry['request_observations'])
    if isinstance(reasons, dict):
        result['rejected_reason_counts'] = {str(k)[:60]: v for k,v in list(reasons.items())[:12]
                                            if isinstance(v,int) and not isinstance(v,bool) and v >= 0}
    for key in ('coverage', 'component_statuses'):
        value = entry.get(key)
        if isinstance(value, dict):
            result[key] = {
                str(name)[:80]: ({str(k): v[:160] if isinstance(v, str) else v for k, v in item.items()
                                 if k in {'status', 'as_of', 'provider', 'reason_code', 'series_id', 'error_kind',
                                          'fetched_at_epoch', 'stale', 'cache_hit', 'retry_after_epoch',
                                          'observation_status', 'observation_age_days', 'date_status', 'retrieval_status', 'page_kind',
                                          'http_status', 'response_sha256', 'response_bytes', 'parser_version',
                                          'primary_provider', 'primary_status', 'fallback_status'}
                                 and isinstance(v, (str, bool, int, float))
                                 and (not isinstance(v, (int, float)) or math.isfinite(v))}
                                if isinstance(item, dict) else item[:80])
                for name, item in list(value.items())[:20] if isinstance(item, (dict, str))
            }
    return result
