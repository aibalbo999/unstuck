"""Bounded Sanyang corporate + SYM global originals; one issuer publisher.

This adapter never caches a bundle, mutates a record, or upgrades a partial
component to a fresh acquisition. The existing corporate route remains intact.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import re
import time
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError
from . import issuer_news as corporate
from . import sym_issuer_news as global_news

POLICY = 'sanyang-issuer-news-bundle-v1'
TICKER = '2206.TW'
PUBLISHER = '三陽工業官網'
MAX_RECORDS = 5
RAW_TTL = 1800
TOTAL_SECONDS = 25
TAIPEI = ZoneInfo('Asia/Taipei')
NAMES = ('corporate', 'global')
STATUSES = {'success', 'skipped_fresh_cache', 'degraded_enrichment', 'error', 'unavailable', 'not_attempted'}
FIELDS = ('selection_policy', 'parser_version', 'component_audits', 'component_records',
          'component_receipts', 'record_bindings', 'status', 'coverage_status', 'window_complete',
          'http_request_sent', 'http_request_count', 'event_kind', 'cache_hit', 'stale',
          'record_count', 'usable_count', 'fetched_at_epoch', 'bundle_error_kind',
          'excluded_reason_counts')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _epoch(value, observed):
    try:
        return type(value) in (int, float) and math.isfinite(value) and 0 <= observed - value < RAW_TTL
    except (ValueError, OverflowError):
        return False


def _component_url(name, url):
    if not isinstance(url, str):
        return False
    if name == 'corporate':
        return url in (corporate.ROSTER_URL, corporate.SANYANG_INDEX) or bool(re.fullmatch(r'https://www\.sanyang\.com\.tw/busnessnews-page[1-9]\d{0,7}', url))
    return url in (global_news.MASTER, global_news.master.JSON_URL, *global_news.CHAIN.values()) or bool(global_news.ARTICLE.fullmatch(url))


def _component_fresh(component, observed, name):
    """The existing company-master cache owns its expiry, independently of news.

    Re-read the same complete cached master and original timestamp. A caller's
    cache flag cannot extend its lifetime, and article receipts keep RAW_TTL.
    """
    if component.get('cache_source') == 'official-company-roster:v2:.TW':
        if (name != 'corporate' or component.get('url') != corporate.ROSTER_URL
                or component.get('http_request_sent') is not False
                or component.get('cache_hit') is not True or component.get('stale') is not False):
            return False
        from .official_company_legal_name import read_cached_listed_roster_bytes
        cached = read_cached_listed_roster_bytes()
        if cached is None:
            return False
        _, metadata = cached
        return all(component.get(key) == value for key, value in metadata.items())
    stamp = component.get('fetched_at_epoch')
    return stamp is None or _epoch(stamp, observed)


def _audit_valid(audit, records, observed, name):
    if (not isinstance(audit, dict) or audit.get('status') not in STATUSES
            or not isinstance(records, list) or len(records) > MAX_RECORDS
            or type(audit.get('record_count')) is not int or audit['record_count'] != len(records)
            or type(audit.get('usable_count')) is not int or audit['usable_count'] != len(records)
            or type(audit.get('http_request_count')) is not int or audit['http_request_count'] < 0
            or type(audit.get('http_request_sent')) is not bool
            or audit['http_request_sent'] != bool(audit['http_request_count'])
            or type(audit.get('cache_hit')) is not bool or type(audit.get('stale')) is not bool
            or audit.get('window_complete') is not False or audit.get('coverage_status') != 'partial'):
        return False
    components = audit.get('component_receipts')
    if not isinstance(components, list) or len(components) > 32:
        return False
    if any(not isinstance(c, dict) or type(c.get('http_request_sent')) is not bool
           or not _component_url(name, c.get('url'))
           or c.get('error_kind') is not None and not isinstance(c['error_kind'], str)
           or c.get('http_status') is not None and (type(c['http_status']) is not int or not 100 <= c['http_status'] <= 599)
           for c in components):
        return False
    if sum(c['http_request_sent'] for c in components) != audit['http_request_count']:
        return False
    epochs = [c['fetched_at_epoch'] for c in components if c.get('fetched_at_epoch') is not None]
    if any(not _component_fresh(c, observed, name) for c in components):
        return False
    shared = [c for c in components if c.get('cache_source') == 'official-company-roster:v2:.TW']
    if shared and (len(shared) != 1 or any(
            (r.get('issuer_news_receipt') or {}).get('master_response_sha256') != shared[0]['source_payload_sha256']
            for r in records)):
        return False
    if audit.get('fetched_at_epoch') != (min(epochs) if epochs else None):
        return False
    if records and (not epochs or audit['status'] in {'error', 'unavailable', 'not_attempted'}):
        return False
    if audit['status'] == 'skipped_fresh_cache' and (audit['http_request_count'] or audit['cache_hit'] is not True):
        return False
    return True


def _body(record, audit, observed):
    url = record.get('source_document_url')
    matches = [c for c in audit['component_receipts'] if c.get('url') == url]
    if len(matches) != 1:
        raise ValueError('body_observation_unverified')
    body = matches[0]
    if (not _epoch(body.get('fetched_at_epoch'), observed) or type(body.get('cache_hit')) is not bool
            or body.get('stale') is True or body.get('error_kind')
            or not (body['cache_hit'] and not body['http_request_sent'] or
                    not body['cache_hit'] and body['http_request_sent'])):
        raise ValueError('body_acquisition_unverified')
    proof = record.get('issuer_news_receipt') or {}
    if body.get('response_sha256') is not None and body['response_sha256'] != proof.get('article_response_sha256'):
        raise ValueError('body_hash_mismatch')
    if global_news.is_marked(record):
        original = proof['source_record_archive']['article']
        if body['fetched_at_epoch'] != original['retrieved_at'] or _json(body.get('original_receipt')) != _json(original):
            raise ValueError('body_receipt_mismatch')
    return body


def _verified(record, name, data, today):
    if not isinstance(record, dict):
        return False
    if global_news.is_marked(record):
        return name == 'global' and global_news.verified_record(record, data, today=today, max_age=RAW_TTL) == PUBLISHER
    return name == 'corporate' and corporate.verified_issuer_news(record, data, today=today) is not None


def _derive(component_records, component_audits, data, today, *, bundle_error_kind='', verify=True):
    if set(component_records) != set(NAMES) or set(component_audits) != set(NAMES):
        raise ValueError('bundle_components_invalid')
    observed = time.time()
    records, bindings, bodies, receipts, epochs = [], [], [], [], []
    excluded = {'duplicate': 0, 'incoming_limit': 0}
    error = bool(bundle_error_kind)
    sent = 0
    for name in NAMES:
        items, audit = component_records[name], component_audits[name]
        if not _audit_valid(audit, items, observed, name):
            raise ValueError('component_audit_invalid')
        error = error or audit['status'] in {'error', 'degraded_enrichment'} or bool(audit.get('error_kind')) or audit['stale']
        error = error or any(c.get('error_kind') or c.get('stale') is True
                             or type(c.get('http_status')) is int and c['http_status'] >= 400
                             for c in audit['component_receipts'])
        sent += audit['http_request_count']
        receipts.extend(deepcopy(audit['component_receipts']))
        if audit['fetched_at_epoch'] is not None:
            epochs.append(audit['fetched_at_epoch'])
        for record in items:
            if verify and not _verified(record, name, data, today):
                raise ValueError('record_original_unverified')
            body = _body(record, audit, observed)
            if any(r['source_document_url'] == record['source_document_url'] for r in records):
                excluded['duplicate'] += 1
                continue
            if len(records) == MAX_RECORDS:
                excluded['incoming_limit'] += 1
                continue
            records.append(deepcopy(record));bodies.append(body)
            bindings.append({'component': name, 'record_sha256': sha256(_json(record).encode()).hexdigest()})
    cached = bool(bodies) and all(b['cache_hit'] for b in bodies)
    new_body = any(not body['cache_hit'] and component_audits[binding['component']]['status'] == 'success'
                   for body, binding in zip(bodies, bindings))
    if records:
        status = ('degraded_enrichment' if error else 'skipped_fresh_cache' if cached and not sent
                  else 'success' if new_body else 'degraded_enrichment')
    else:
        status = 'error' if error else 'unavailable'
    # Do not relabel a new index/empty branch as acquisition of reused articles.
    reason = bundle_error_kind or ('component_degraded' if error else 'warm_records_only' if records and cached and sent else '')
    return records, {'selection_policy': POLICY, 'parser_version': POLICY,
                     'component_audits': deepcopy(component_audits), 'component_records': deepcopy(component_records),
                     'component_receipts': receipts, 'record_bindings': bindings,
                     'status': status, 'coverage_status': 'partial', 'window_complete': False,
                     'http_request_sent': bool(sent), 'http_request_count': sent,
                     'event_kind': 'http_request' if sent else 'cache_hit' if cached else 'local_block',
                     'cache_hit': cached, 'stale': False, 'record_count': len(records), 'usable_count': len(records),
                     'fetched_at_epoch': min(epochs) if epochs else None, 'bundle_error_kind': reason,
                     'excluded_reason_counts': excluded}


def _empty(status, reason=''):
    return {'status': status, 'error_kind': reason, 'record_count': 0, 'usable_count': 0,
            'http_request_sent': False, 'http_request_count': 0, 'event_kind': 'local_block',
            'cache_hit': False, 'stale': False, 'fetched_at_epoch': None,
            'coverage_status': 'partial', 'window_complete': False, 'component_receipts': []}


def _fresh_all(value, audit):
    observed = time.time()
    return (all(_component_fresh(c, observed, name)
                for name in NAMES for c in audit['component_audits'][name]['component_receipts'])
            and all(not global_news.is_marked(r) or global_news._fresh(r['issuer_news_receipt']['source_record_archive'], RAW_TTL, observed) for r in value))


def fetch_recent_sanyang_news(*, now=None, corporate_http=None, global_http=None):
    end = time.monotonic() + TOTAL_SECONDS
    now = now or datetime.now(TAIPEI)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return [], {**_empty('error', 'invalid_time'), 'selection_policy': POLICY, 'parser_version': POLICY}
    today = now.astimezone(TAIPEI).date()
    records = {name: [] for name in NAMES}
    audits = {name: _empty('not_attempted', 'incoming_limit') for name in NAMES}
    bundle_error = ''
    for name in NAMES:
        remaining = MAX_RECORDS - len(records['corporate'])
        if name == 'global' and remaining <= 0:
            audits[name] = _empty('not_attempted')
            audits[name]['not_attempted_reason'] = 'incoming_limit'
            break
        if time.monotonic() >= end:
            audits[name] = _empty('error', 'timeout');bundle_error = 'timeout';break
        branch_deadline = min(end, time.monotonic() + 20) if name == 'corporate' else end
        http = corporate_http if name == 'corporate' else global_http
        if http is None:
            http = corporate.IssuerNewsHttp(branch_deadline) if name == 'corporate' else global_news.SymNewsHttp(end)
        if hasattr(http, 'deadline'):
            http.deadline = min(http.deadline, branch_deadline)
        try:
            if name == 'corporate':
                items, audit = corporate.fetch_recent_issuer_news(TICKER, now=now, http=http)
            else:
                items, audit = global_news.fetch_recent_news(now=now, http=http, deadline=end, limit=remaining)
            records[name], audits[name] = items, audit
        except (OSError, ValueError, TypeError, AttributeError, KeyError, SourceResponseError) as exc:
            components = deepcopy(getattr(http, 'components', []))
            stamps = [c['fetched_at_epoch'] for c in components if c.get('fetched_at_epoch') is not None]
            sent = getattr(http, 'http_request_count', 0)
            audits[name] = {**_empty('error', getattr(exc, 'error_kind', 'component_error')),
                            'http_request_sent': bool(sent), 'http_request_count': sent,
                            'fetched_at_epoch': min(stamps) if stamps else None, 'component_receipts': components}
    if time.monotonic() >= end:
        bundle_error = 'timeout'
    try:
        value, audit = _derive(records, audits, {'ticker': TICKER}, today, bundle_error_kind=bundle_error)
        if time.monotonic() >= end and not bundle_error:
            value, audit = _derive(records, audits, {'ticker': TICKER}, today, bundle_error_kind='timeout', verify=False)
        # One final instant checks age after all original replay/diagnostic copies.
        if not _fresh_all(value, audit):
            raise ValueError('original_expired')
        return value, audit
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError) as exc:
        # Preserve all evidence for diagnosis, but never return unbound records.
        return [], {**_empty('error', str(exc)[:100]), 'selection_policy': POLICY, 'parser_version': POLICY,
                    'event_kind': 'http_request' if any(a.get('http_request_sent') for a in audits.values()) else 'local_block',
                    'component_audits': deepcopy(audits), 'component_records': deepcopy(records),
                    'component_receipts': [deepcopy(c) for a in audits.values() for c in a.get('component_receipts', [])],
                    'http_request_count': sum(a.get('http_request_count', 0) for a in audits.values()),
                    'http_request_sent': any(a.get('http_request_sent') for a in audits.values())}


def guard_bundle(value, audit, data):
    """Read-only current-original check for the narrow source-only partial merge."""
    try:
        if (not global_news.validate_context(data) or not isinstance(value, list) or not 1 <= len(value) <= MAX_RECORDS
                or not isinstance(audit, dict) or audit.get('selection_policy') != POLICY
                or audit.get('bundle_error_kind') not in {'', 'timeout', 'warm_records_only', 'component_degraded'}):
            return False
        records, expected = _derive(audit['component_records'], audit['component_audits'], data,
                                    datetime.fromtimestamp(time.time(), TAIPEI).date(),
                                    bundle_error_kind='timeout' if audit['bundle_error_kind'] == 'timeout' else '')
        return (_json(value) == _json(records) and all(_json(audit.get(k)) == _json(expected[k]) for k in FIELDS)
                and _fresh_all(records, expected))
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError):
        return False
