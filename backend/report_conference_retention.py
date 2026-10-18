"""Keep a report's verified historical conference after a transient new failure."""
from copy import deepcopy
from datetime import datetime, timezone
import time
import zlib

from conference_historical_evidence import (PROFILES, canonical, digest, profile,
    replay_historical_conference, compatible_incoming_originals)
from data_freshness import build_source_freshness_entry
from data_trust import finalize_data_trust

POLICY = 'report-local-historical-conference-retention.v1'
TRANSIENT_ERRORS = frozenset({'timeout', 'transport_error', 'server_error', 'cooldown'})
NOTE_PREFIX = '法說原件沿用此報告歷史證據：'
REUSE_PROVIDER = 'Saved verified historical conference'


def _identity(data, ticker, module):
    if not isinstance(data, dict) or data.get('ticker') != ticker or not module.validate_context(data, ticker):
        return False
    allowed = {'ticker': ticker, 'stock_id': ticker.split('.')[0], 'quote_type': 'EQUITY',
               'quoteType': 'EQUITY', 'instrument_type': 'EQUITY'}
    identity = data.get('company_identity')
    if identity is not None and not isinstance(identity, dict):
        return False
    return all(row.get(key) in (None, '', value) for row in (data, identity or {})
               for key, value in allowed.items())


def _origin(snapshot, ticker, module, deadline):
    from report_source_refresh import _timestamp
    old = snapshot.get('data')
    if snapshot.get('ticker') != ticker or not _identity(old, ticker, module):
        return None
    value = old.get('earnings_call')
    retained = old.get('conference_retention')
    if retained is not None:
        if (not isinstance(retained, dict) or retained.get('policy') != POLICY
                or retained.get('ticker') != ticker or retained.get('new_acquisition') is not False):
            return None
        audit = retained.get('original_audit')
    else:
        candidates = []
        for parent in (snapshot, old):
            audits = parent.get('source_audit')
            if not isinstance(audits, list) or any(not isinstance(a, dict) for a in audits):
                return None
            candidates += [a for a in audits if a.get('source') == 'earnings_call'
                           and a.get('provider') == module.PROVIDER]
        unique = {canonical(a): a for a in candidates}
        if len(unique) != 1:
            return None
        audit = next(iter(unique.values()))
    evidence = replay_historical_conference(value, ticker, audit, deadline=deadline)
    epochs = [evidence['original_observation_epoch']]
    for parent in (snapshot, old):
        fresh = parent.get('source_freshness', {})
        if not isinstance(fresh, dict):
            return None
        entry = fresh.get('earnings_call')
        if entry is not None:
            stamp = _timestamp(entry) if isinstance(entry, dict) else None
            if stamp is None:
                return None
            epochs.append(stamp)
    stamp = min(epochs)
    if retained is not None and (retained.get('original_audit_sha256') != digest(audit)
            or retained.get('original_context_sha256') != digest(value)
            or retained.get('original_fetched_at_epoch') != stamp
            or canonical(retained.get('historical_evidence')) != canonical(evidence)):
        return None
    return value, audit, stamp, evidence


def retain_verified_conference(snapshot, incoming, ticker):
    """Report-local copy only. No provider calls, cache writes or SLA recording."""
    try:
        deadline = time.monotonic() + 10.
        if ticker not in PROFILES:
            return incoming
        module, _, _ = profile(ticker)
        if not _identity(incoming, ticker, module):
            return incoming
        value = incoming.get('earnings_call')
        # Any new publication/material/event information requires reconciliation;
        # do not hide it behind the report's old successful publication.
        if value is not None and (not isinstance(value, dict) or value):
            return incoming
        if incoming.get('conference_retention') is not None:
            return incoming
        audits = incoming.get('source_audit')
        if not isinstance(audits, list) or any(not isinstance(a, dict) for a in audits):
            return incoming
        conference = [a for a in audits if a.get('source') == 'earnings_call']
        if not conference or any(
                a.get('provider') != module.PROVIDER or a.get('ticker') not in (None, ticker)
                or a.get('status') != 'error' or a.get('error_kind') not in TRANSIENT_ERRORS
                or type(a.get('record_count')) is not int or a['record_count'] != 0
                or a.get('http_status') in (401, 403, 429)
                or any(a.get(k) for k in ('documents', 'materials', 'original_receipt', 'selected', 'event_date'))
                for a in conference):
            return incoming
        # A component's terminal failure or newly selected event must not be
        # concealed by a parent's generic transient error label.
        for audit in conference:
            components = audit.get('component_statuses', [])
            if not isinstance(components, list) or any(not isinstance(c, dict) for c in components):
                return incoming
            if any(c.get('http_status') in (401, 403, 429)
                   or c.get('error_kind') not in (None, '', *TRANSIENT_ERRORS)
                   or any(c.get(k) for k in ('documents', 'materials', 'selected', 'event_date'))
                   for c in components):
                return incoming
        origin = _origin(snapshot, ticker, module, deadline)
        if origin is None:
            return incoming
        old_value, audit, stamp, evidence = origin
        compatible_incoming_originals(old_value, ticker, conference, deadline=deadline)
        merged = deepcopy(incoming)
        merged['earnings_call'] = deepcopy(old_value)
        freshness = merged.get('source_freshness')
        if not isinstance(freshness, dict):
            return incoming
        fresh = build_source_freshness_entry('earnings_call', ticker, stamp, cache_hit=True,
                                             now_epoch=time.time())
        fresh.update(stale=True, is_fresh=False, fetch_is_fresh=False,
                     coverage_status='retained_historical_original')
        freshness['earnings_call'] = fresh
        reuse = {'source': 'earnings_call', 'provider': REUSE_PROVIDER, 'ticker': ticker,
                 'status': 'degraded_enrichment', 'record_count': 1, 'event_kind': 'cache_hit',
                 'cache_hit': True, 'stale': True, 'http_request_sent': False, 'http_request_count': 0,
                 'fetched_at_epoch': stamp, 'fetched_at': datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                 'message': '本次來源取得失敗；沿用此報告已重播的歷史原件，並非新取得。'}
        merged['source_audit'] = [reuse, *merged['source_audit']]
        merged['conference_retention'] = {
            'policy': POLICY, 'ticker': ticker, 'original_audit': deepcopy(audit),
            'original_audit_sha256': digest(audit), 'original_context_sha256': digest(old_value),
            'original_fetched_at_epoch': stamp, 'historical_evidence': evidence,
            'failed_refresh_audits': deepcopy(conference), 'new_acquisition': False,
        }
        notes = merged.get('data_source_notes', [])
        if not isinstance(notes, list) or any(not isinstance(n, str) for n in notes):
            return incoming
        merged['data_source_notes'] = [NOTE_PREFIX + fresh['fetched_at']
            + '；原生正文與限制整包保留，資料明示過期；本次失敗不改寫原取得時間或計為成功。',
            *[n for n in notes if not n.startswith(NOTE_PREFIX)]]
        finalize_data_trust(merged)
        if time.monotonic() >= deadline:
            return incoming
        return merged
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError,
            OSError, EOFError, RuntimeError, zlib.error, RecursionError):
        return incoming


def retire_conference_retention(data):
    """Called only after the source-only service verified a new conference."""
    if not isinstance(data, dict) or 'conference_retention' not in data:
        return data
    result = deepcopy(data)
    origin = result.pop('conference_retention')
    archive = result.get('conference_retention_archive', [])
    if not isinstance(archive, list):
        archive = [archive]
    result['conference_retention_archive'] = [*archive, origin]
    notes = result.get('data_source_notes')
    if isinstance(notes, list):
        result['data_source_notes'] = [n for n in notes if not isinstance(n, str) or not n.startswith(NOTE_PREFIX)]
    return result
