"""Retain a report's replayable official annual series after transport failure.

This is report-local reuse, never an acquisition, provider cache, or promotion
of a partial series. Only the MOPS JSON contract replays all original bytes.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import time

from annual_financial_source_refresh import apply_annual_history_values
from data_fetch.annual_financial_source_provider import HISTORY_FIELDS, SCHEMA, validate_context
from data_fetch.market_sources.mops_public_annual import PROVIDER, SOURCE_URL, project_public_history
from data_freshness import build_source_freshness_entry
from data_trust import finalize_data_trust

POLICY = 'report-local-verified-mops-annual-retention.v1'
TRANSIENT_ERRORS = frozenset({'timeout', 'transport_error', 'server_error', 'cooldown'})
PROOF_FIELDS = ('source_url', 'documents', 'raw_twd_by_year', 'comparative_revisions', 'comparative_coverage')


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _compatible(row, ticker):
    if not isinstance(row, dict):
        return False
    allowed = {'ticker': (ticker,), 'stock_id': (ticker.split('.')[0],),
               'schema': (SCHEMA,), 'statement_schema': (SCHEMA,),
               'currency': ('TWD',), 'financial_currency': ('TWD',),
               'report_scope': ('consolidated',), 'quote_type': ('EQUITY',),
               'quoteType': ('EQUITY',), 'instrument_type': ('EQUITY',)}
    if any(k in row and row[k] is not None and row[k] not in values for k, values in allowed.items()):
        return False
    identity = row.get('company_identity')
    if identity is not None:
        return isinstance(identity, dict) and all(
            k not in identity or identity[k] is None or identity[k] in allowed[k]
            for k in ('ticker', 'stock_id', 'instrument_type'))
    return True


def _origin(snapshot, ticker):
    from report_source_refresh import _timestamp
    old = snapshot.get('data')
    if not isinstance(old, dict) or snapshot.get('ticker') != ticker:
        return None
    validate_context(old, ticker)
    if not _compatible(old, ticker) or old.get('sector_specific_financials') or old.get('financial_history_basis'):
        return None
    retained = old.get('annual_history_retention')
    if retained is not None:
        if not isinstance(retained, dict) or retained.get('policy') != POLICY:
            return None
        candidates = [retained.get('original_audit')]
    else:
        candidates = [a for a in snapshot.get('source_audit', []) if isinstance(a, dict)
                      and a.get('source') == 'financial_statements' and a.get('provider') == PROVIDER]
    if len(candidates) != 1 or not isinstance(candidates[0], dict):
        return None
    audit = candidates[0]
    if (audit.get('source') != 'financial_statements' or audit.get('provider') != PROVIDER
            or audit.get('ticker') != ticker or audit.get('status') != 'success'
            or type(audit.get('record_count')) is not int or audit['record_count'] != 5
            or audit.get('source_url') != SOURCE_URL or audit.get('stale') is True):
        return None
    if not _compatible(audit, ticker):
        return None
    stamp = _timestamp(audit)
    if stamp is None:
        return None
    value = {**{k: deepcopy(old[k]) for k in HISTORY_FIELDS},
             **{k: deepcopy(audit[k]) for k in PROOF_FIELDS if k in audit},
             'schema': SCHEMA, 'ticker': ticker, 'currency': 'TWD', 'report_scope': 'consolidated'}
    projected = project_public_history(value, ticker)
    if projected is None:
        return None
    # The original provider observation cannot predate its component originals.
    epochs = [part[key]['retrieved_at'] for doc in value['documents'] for part in doc['components']
              for key in ('raw_receipt', 'unit_template_receipt')]
    if any(type(n) not in (int, float) or n > stamp for n in epochs):
        return None
    original_epochs = [stamp]
    for parent in (snapshot, old):
        freshness = parent.get('source_freshness', {})
        if not isinstance(freshness, dict):
            return None
        entry = freshness.get('financial_statements')
        if entry is not None:
            if not isinstance(entry, dict):
                return None
            earlier = _timestamp(entry)
            if earlier is None:
                return None
            original_epochs.append(earlier)
    retained_epoch = min(original_epochs)
    if retained is not None and (retained.get('original_audit_sha256') != _digest(audit)
            or retained.get('original_fetched_at_epoch') != retained_epoch):
        return None
    return projected, audit, retained_epoch


def retain_verified_annual_history(snapshot, incoming, ticker):
    """Return a copy only when a transient failure would discard proven years."""
    try:
        validate_context(incoming, ticker)
        if not _compatible(incoming, ticker) or incoming.get('sector_specific_financials') or incoming.get('financial_history_basis'):
            return incoming
        years = incoming.get('years')
        if (not isinstance(years, list) or len(years) >= 5
                or any(type(y) is not str for y in years) or years != sorted(set(years))):
            return incoming
        audits = incoming.get('source_audit')
        if not isinstance(audits, list) or any(not isinstance(a, dict) for a in audits):
            return incoming
        financial = [a for a in audits if a.get('source') == 'financial_statements']
        official = [a for a in financial if a.get('provider') == PROVIDER]
        if any(not _compatible(a, ticker) for a in financial):
            return incoming
        if (len(official) != 1 or official[0].get('status') != 'error'
                or official[0].get('error_kind') not in TRANSIENT_ERRORS
                or type(official[0].get('record_count')) is not int or official[0]['record_count'] != 0
                or official[0].get('ticker') not in (None, ticker)
                or official[0].get('http_status') in (401, 403, 429)):
            return incoming
        # New official facts, restatements, or scope changes require reconciliation,
        # even when their series is incomplete. Never silently prefer old numbers.
        if any(a.get(k) for a in [incoming, *financial] for k in PROOF_FIELDS[1:]):
            return incoming
        origin = _origin(snapshot, ticker)
        if origin is None:
            return incoming
        projected, audit, stamp = origin
        if not set(years).issubset(projected['years']):
            return incoming
        merged = deepcopy(incoming)
        apply_annual_history_values(merged, projected, projected, incoming, basis_label='沿用已核對官方')
        fresh = build_source_freshness_entry('financial_statements', ticker, stamp,
                                            cache_hit=True, now_epoch=time.time())
        source_freshness = merged.get('source_freshness')
        if not isinstance(source_freshness, dict):
            return incoming
        source_freshness['financial_statements'] = fresh
        # Preserve the failed acquisition unchanged and last in its source order.
        # The reuse row has no new HTTP/operation/attempt identity or SLA event.
        reuse = {'source': 'financial_statements', 'provider': 'Saved verified MOPS annual history',
                 'ticker': ticker, 'status': 'degraded_enrichment', 'event_kind': 'cache_hit',
                 'cache_hit': True, 'stale': fresh['stale'], 'record_count': 5,
                 'fetched_at_epoch': stamp, 'fetched_at': datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                 'http_request_sent': False, 'http_request_count': 0, 'http_status': None,
                 'message': '本次官方財報取得失敗；重播並沿用此報告保存的五年原件，非新取得。',
                 **{k: deepcopy(projected[k]) for k in PROOF_FIELDS if k in projected}}
        merged['source_audit'] = [reuse, *merged['source_audit']]
        merged['annual_history_retention'] = {
            'policy': POLICY, 'ticker': ticker, 'original_audit': deepcopy(audit),
            'original_audit_sha256': _digest(audit), 'original_fetched_at_epoch': stamp,
            'original_years': deepcopy(projected['years']), 'new_acquisition': False,
            'partial_provider_history': {k: deepcopy(incoming.get(k)) for k in HISTORY_FIELDS},
            'failed_refresh_audit': deepcopy(official[0]),
        }
        notes = merged.get('data_source_notes', [])
        if not isinstance(notes, list) or any(not isinstance(n, str) for n in notes):
            return incoming
        prefix = '年度財報沿用此報告已核對原件：'
        note = (prefix + fresh['fetched_at'] + '；本次下載失敗，五年數列整包保留、未混入部分年度備援值。'
                '原取得時間與過期狀態保持；即時／TTM純量沿本次其他來源，分析本文未重跑。')
        merged['data_source_notes'] = [note, *[n for n in notes if not n.startswith(prefix)]]
        finalize_data_trust(merged)
        return merged
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        # A missing/corrupt historical original never promotes unverified data.
        return incoming
