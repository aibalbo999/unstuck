"""Bounded structured source evidence; never persist credentials or response bodies."""
from __future__ import annotations

import math
from hashlib import sha256
from itertools import islice
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


def _original_http_receipts(entry):
    """Summarize existing original receipts; never infer a current HTTP send.

    Original response metadata and this invocation's cache/send state remain
    separate. This is passive telemetry, not issuer or parsed-data acceptance.
    """
    candidates = []
    if isinstance(entry.get('raw_http_receipt'), dict):
        candidates.append(('provider_body', entry, entry['raw_http_receipt']))
    components = entry.get('component_statuses')
    values = list(islice(components.values(), 20)) if isinstance(components, dict) else components[:20] if isinstance(components, list) else []
    for index, component in enumerate(values):
        if isinstance(component, dict) and isinstance(component.get('original_receipt'), dict):
            candidates.append((f'component_{index}', component, component['original_receipt']))
    result = []
    for role, current, receipt in candidates[:20]:
        url = receipt.get('source_url')
        digest, size, stamp, status = (receipt.get(key) for key in
            ('raw_response_sha256', 'raw_response_bytes', 'retrieved_at', 'http_status'))
        try:
            parsed = urlsplit(url) if isinstance(url, str) and len(url) <= 4096 else None
            valid = (receipt.get('status') == 'archived'
                and receipt.get('evidence_kind') in {'raw_http_response_bytes', 'decoded_complete_http_response_body'}
                and parsed is not None and parsed.scheme == 'https' and parsed.hostname
                and parsed.username is None and parsed.password is None
                and not any(ord(c) < 32 for c in url)
                and isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest)
                and type(size) is int and 0 < size <= 100_000_000
                and type(stamp) in (int, float) and math.isfinite(stamp) and 0 < stamp <= 1_000_000_000_000
                and type(status) is int and 100 <= status <= 599)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            continue
        try:
            url_digest = sha256(url.encode('utf-8', 'strict')).hexdigest()
        except UnicodeError:
            continue
        row = {'role': role, 'source_url_sha256': url_digest,
               'response_sha256': digest, 'response_bytes': size,
               'original_retrieved_at_epoch': stamp, 'http_status': status,
               'evidence_kind': receipt['evidence_kind']}
        for key in ('http_request_sent', 'cache_hit'):
            if type(current.get(key)) is bool:
                row[key] = current[key]
        for key in ('http_status_observed', 'response_complete'):
            if type(receipt.get(key)) is bool:
                row[key] = receipt[key]
        if type(receipt.get('cache_hit')) is bool:
            row['original_cache_hit'] = receipt['cache_hit']
        if isinstance(receipt.get('request_method'), str) and receipt['request_method'] in {'GET', 'POST'}:
            row['request_method'] = receipt['request_method']
        result.append(row)
    return result


def _getac_transport_steps(value):
    """Keep bounded stage facts, never URLs, bodies, headers or free-form errors."""
    stages = {
        'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv': 'master_csv',
        'https://openapi.twse.com.tw/v1/opendata/t187ap03_L': 'master_json',
        'https://www.getacgroup.com': 'registered_root',
        'https://en.getacgroup.com/investors/calendar.php?index_year=2026': 'conference_index',
        'https://en.getacgroup.com/upload/document_investor_calendar_list_files/a595874cfc02bb78ae85a5d21150c0b0.pdf': 'presentation_pdf',
    }
    errors = {'timeout','transport_error','server_error','cooldown','single_flight_busy',
              'original_expired','rate_limit','access_denied','parse_error','original_unverified'}
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:12]:
        if not isinstance(item, dict) or not isinstance(item.get('url'), str) or item['url'] not in stages:
            continue
        row = {'stage': stages[item['url']]}
        for k in ('http_request_sent','cache_hit'):
            if type(item.get(k)) is bool:
                row[k] = item[k]
        for k in ('http_status','response_bytes'):
            v = item.get(k)
            if type(v) is int and (100 <= v <= 599 if k == 'http_status' else 0 <= v <= 8*1024*1024):
                row[k] = v
        if isinstance(item.get('error_kind'), str) and item['error_kind'] in errors:
            row['error_kind'] = item['error_kind']
        digest = item.get('response_sha256')
        if isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest):
            row['response_sha256'] = digest
        result.append(row)
    return result


def _peer_candidate_diagnostics(entry):
    """Typed TW peer gaps only; no values, bodies, URLs or exception messages."""
    if entry.get('source') != 'dynamic_peer_metrics' or entry.get('provider') != 'FinMind/yfinance':
        return []
    values = entry.get('candidate_diagnostics')
    if not isinstance(values, list):
        return []
    fields = {'gross_margin_pct', 'operating_margin_pct', 'profit_margin_pct', 'roe_pct',
              'asset_turnover', 'pe_ttm', 'pb', 'ps_ttm'}
    providers = {'yfinance', 'FinMind TaiwanStockPER', 'TWSE/TPEx official peer valuation OpenAPI',
                 'Yahoo annual financial statements'}
    statuses = {'success', 'not_needed', 'empty_response', 'download_failed', 'missing_matching_annual_values',
                'identity_mismatch', 'not_equity', 'unavailable', 'valid_empty', 'conflicting_observations',
                'metrics_missing', 'not_applicable', 'rate_limited', 'cache_hit'}
    comparisons = {'business_industry_matched', 'business_industry_mismatch', 'identity_unverified',
                   'industry_candidate_only', 'profile_ranked', 'heuristic_unverified',
                   'official_convenience_candidate', 'official_segment_candidate', 'published_segment_candidate'}
    out = []
    for item in values[:10]:
        if not isinstance(item, dict):
            continue
        ticker, status = item.get('ticker'), item.get('metrics_status')
        if (not isinstance(ticker, str) or len(ticker) > 10 or not re.fullmatch(r'[1-9][0-9]{3,5}\.(?:TW|TWO)', ticker)
                or not isinstance(status, str) or len(status) > 16 or status not in {'complete', 'partial', 'unavailable'}):
            continue
        row = {'ticker': ticker, 'metrics_status': status}
        if type(item.get('selected')) is bool:
            row['selected'] = item['selected']
        comparison = item.get('comparison_status')
        if isinstance(comparison, str) and len(comparison) <= 64 and comparison in comparisons:
            row['comparison_status'] = comparison
        missing = item.get('missing_metrics')
        if isinstance(missing, list):
            row['missing_metrics'] = list(dict.fromkeys(v for v in missing[:32] if isinstance(v, str) and len(v) <= 32 and v in fields))
        attempts = item.get('acquisition_attempts')
        if isinstance(attempts, list):
            kept = []
            for attempt in attempts[:6]:
                if not isinstance(attempt, dict):
                    continue
                provider, outcome = attempt.get('provider'), attempt.get('status')
                if not isinstance(provider, str) or len(provider) > 80 or provider not in providers or not isinstance(outcome, str):
                    continue
                if outcome.startswith('download_failed:'):
                    outcome = 'download_failed'
                if len(outcome) > 80 or outcome not in statuses:
                    continue
                result = {'provider': provider, 'status': outcome}
                if type(attempt.get('cache_hit')) is bool:
                    result['cache_hit'] = attempt['cache_hit']
                day = attempt.get('observed_at')
                if isinstance(day, str) and re.fullmatch(r'20[0-9]{2}-[0-9]{2}-[0-9]{2}', day):
                    from datetime import date
                    try:
                        result['observed_at'] = date.fromisoformat(day).isoformat()
                    except ValueError:
                        pass
                kept.append(result)
            row['acquisition_attempts'] = kept
        out.append(row)
    return out


def observation_details(entry: dict) -> dict:
    result = correlation_metadata(entry)
    peer_gaps = _peer_candidate_diagnostics(entry)
    if peer_gaps:
        result['candidate_diagnostics'] = peer_gaps
    originals = _original_http_receipts(entry)
    if originals:
        result['original_http_receipts'] = originals
    try:
        from finmind_monthly_lineage import audit_lineage
        lineage=audit_lineage(entry)
    except Exception:lineage=None
    if lineage is not None:result['sdk_payload_lineage']=lineage
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
    if entry.get('provider') == 'Getac official conference presentation':
        result['transport_steps'] = _getac_transport_steps(entry.get('component_statuses'))
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
