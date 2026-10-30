"""Refresh job observations through the existing free provider and trust gates."""
from copy import deepcopy
import math
import re
import time

from fastapi import HTTPException

SOURCE = 'alternative_data'
PROVIDER = '104 & 1111 job openings'
IDENTITY_FIELDS = ('ticker', 'company_name', 'company_identity', 'quote_type', 'quoteType', 'instrument_type', 'stock_id')


def validate_alternative_refresh_context(data, ticker):
    identity = data.get('company_identity') if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get('ticker') != ticker
            or not isinstance(ticker, str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW(?:O)?', ticker)
            or not isinstance(identity, dict) or identity.get('ticker') != ticker
            or identity.get('stock_id') not in (None, '', ticker.split('.')[0])
            or data.get('stock_id') not in (None, '', ticker.split('.')[0])
            or identity.get('instrument_type') != 'EQUITY' or data.get('quote_type') != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quoteType'))
            or not isinstance(identity.get('official_name'), str) or not identity['official_name'].strip()
            or not isinstance(data.get('company_name'), str) or not data['company_name'].strip()
            or data.get(SOURCE) is not None and not isinstance(data[SOURCE], dict)):
        raise HTTPException(status_code=400, detail='指定職缺刷新須有一致的股票、公司身分與原觀測；原快照保持')
    for key in ('legal_name', 'display_name'):
        if identity.get(key) is not None and not isinstance(identity[key], str):
            raise HTTPException(status_code=400, detail='原公司名稱格式無法安全核對')
    for key in ('allowed_aliases', 'english_names', 'forbidden_aliases'):
        items = identity.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
            raise HTTPException(status_code=400, detail='原公司別名格式無法安全核對')
    names = {identity['official_name'], identity.get('legal_name'), *identity.get('english_names', [])}
    if any(part.strip() not in names for part in data['company_name'].split(' / ')):
        raise HTTPException(status_code=400, detail='原公司搜尋名稱與股票身分不一致')
    for key, kind in (('source_record_archive', dict), ('data_source_notes', str)):
        items = data.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, kind) for x in items):
            raise HTTPException(status_code=400, detail='原來源封存或說明格式無法安全保留')


def valid_alternative_receipt(value, audit, data, *, require_fetch_id=True):
    from data_freshness import source_max_age_seconds
    from data_trust import source_record_count
    from provider_correlation import current_correlation
    from report_source_refresh import _timestamp

    if (not isinstance(value, dict) or not isinstance(audit, dict)
            or audit.get('source') != SOURCE or audit.get('provider') != PROVIDER
            or audit.get('status') not in ('success', 'skipped_fresh_cache')
            or type(audit.get('record_count')) is not int or audit['record_count'] <= 0
            or type(audit.get('cache_hit')) is not bool or audit.get('stale') is not False
            or require_fetch_id and (not isinstance(audit.get('fetch_id'), str) or not audit['fetch_id'])):
        return False
    current = current_correlation()
    if (audit.get('ticker') not in (None, data['ticker'])
            or current.get('fetch_id') and audit.get('fetch_id') not in (None, current['fetch_id'])):
        return False
    if audit['cache_hit'] and audit.get('http_request_sent') is True:
        return False
    if audit['status'] == 'skipped_fresh_cache' and not audit['cache_hit']:
        return False
    stamp = _timestamp(audit)
    ttl = source_max_age_seconds(SOURCE, data['ticker'])
    if stamp is None or not 0 <= time.time() - stamp < ttl:
        return False
    # A recruitment article alone cannot satisfy this job recovery operation.
    jobs = deepcopy(value)
    jobs['recent_recruitment_news'] = []
    for key in ('job_openings_104', 'job_openings_1111'):
        component = jobs.get(key)
        for item in component if isinstance(component, list) else [component]:
            if isinstance(item, dict):
                item['recent_recruitment_news'] = []
    if source_record_count(SOURCE, {**data, SOURCE: jobs}) <= 0:
        return False
    if source_record_count(SOURCE, {**data, SOURCE: value}) != audit['record_count']:
        return False
    official = value.get('job_openings_official')
    if isinstance(official, dict) and official.get('source') == 'KGI Financial Holding official Workday careers':
        from data_fetch.context_provider_cache import _kgi_live_remaining
        if _kgi_live_remaining({'value': value, 'audit': audit}) <= 0:
            return False
    return True


def _failure_diagnostics(value, depth=0):
    """Keep bounded diagnostic evidence safe for the existing SQL/audit writer."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # SQL integers and the writer's int()/isfinite() conversions must agree.
        return value if -2**53 < value < 2**53 and math.isfinite(value) else None
    if isinstance(value, str):
        return value[:4096]
    if depth >= 6:
        return None
    if isinstance(value, dict):
        return {str(k)[:160]: _failure_diagnostics(v, depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, (list, tuple)):
        return [_failure_diagnostics(v, depth + 1) for v in value[:100]]
    return None



def record_related_alternative_attempts(result):
    """Source-only responses keep one merge receipt, but retain child failures.

    The full workflow already flattens related_entries. This adapter serves the
    source-only path, which cannot add diagnostics to its strict one-row merge.
    """
    from provider_sla import record_source_audit_entries
    entries = result.audit.get('related_entries') if isinstance(result.audit, dict) else None
    if not isinstance(entries, list):
        return
    rows = [entry for entry in entries if isinstance(entry, dict)
            and entry.get('source') == SOURCE and entry.get('provider') == 'CHT official public careers'
            and entry.get('status') in {'unavailable', 'error', 'degraded_enrichment'}
            and type(entry.get('record_count')) is int and entry['record_count'] == 0]
    if rows:
        import sqlite3
        from contextlib import suppress
        with suppress(sqlite3.Error):
            record_source_audit_entries(rows)


def guard_alternative_result(result, data):
    from data_fetch.types import ProviderResult
    audit = result.audit if isinstance(result.audit, dict) else {}
    if (result.source == SOURCE and result.provider == PROVIDER
            and result.status in ('success', 'skipped_fresh_cache') and result.status == audit.get('status')
            and valid_alternative_receipt(result.value, audit, data, require_fetch_id=False)):
        return result
    failed_status = result.status if result.status in ('error', 'unavailable', 'degraded_enrichment', 'not_configured') else 'unavailable'
    safe_audit = _failure_diagnostics(audit)
    duration = safe_audit.get('duration_ms')
    safe_audit['duration_ms'] = int(duration) if type(duration) in (int, float) and duration >= 0 else 0
    safe_audit.update(source=SOURCE, provider=PROVIDER, status=failed_status, record_count=0)
    if audit.get('status') != failed_status or result.status in ('success', 'skipped_fresh_cache'):
        safe_audit.update(error_kind='source_refresh_unverified',
                          message='職缺、雇主原件、供應商狀態或取得時間未通過核對；原快照保持。')
    return ProviderResult(SOURCE, PROVIDER, failed_status, value={}, audit=safe_audit)


def merge_alternative_source(old_data, old_audits, value, audits, ticker):
    from report_source_refresh import _reassess_original_freshness
    validate_alternative_refresh_context(old_data, ticker)
    if (not isinstance(audits, list) or len(audits) != 1
            or not valid_alternative_receipt(value, audits[0], old_data)):
        raise HTTPException(status_code=502, detail='指定職缺來源、雇主原件或取得時間未通過核對；原快照保持')
    merged = deepcopy(old_data)
    archive = merged.setdefault('source_record_archive', [])
    if old_data.get(SOURCE) is not None:
        archive.append({'source': SOURCE, 'reason': 'superseded_by_alternative_source_refresh', 'record': deepcopy(old_data[SOURCE])})
    archive.extend({'source': SOURCE, 'reason': 'superseded_by_alternative_source_refresh', 'audit': deepcopy(a)}
                   for a in old_audits if a.get('source') == SOURCE)
    merged[SOURCE] = deepcopy(value)
    merged['source_audit'] = [deepcopy(a) for a in old_audits if a.get('source') != SOURCE] + deepcopy(audits)
    note = '僅更新職缺來源，原件與雇主身分沿既有規則核對；職缺樣本不是招聘人數或全市場總數，分析本文需重新執行。'
    notes = merged.setdefault('data_source_notes', [])
    if note not in notes:
        notes.append(note)
    _reassess_original_freshness(merged, ticker, SOURCE, audits)
    return merged
