"""Annual identity dependency; preserve each caller's historical receipt contract."""
from datetime import datetime, timezone
import math
import time
from hashlib import sha256

from search_provider_runtime import SourceResponseError
from . import official_issuer_master as shared
from .official_issuer_master_transport import IssuerMasterHttp
from .tcfhc_conference_transport import ConferenceHttp as LegacyHoldingHttp

MASTER_URL = shared.MASTER_URL
JSON_URL = shared.JSON_URL
HISTORICAL_MAX_AGE = 100 * 366 * 86400
_SHARED_MARKERS = frozenset({'retrieval_policy', 'response_metadata', 'acquisition_manifest',
                             'wire_original', 'fresh_until_epoch', 'reusable', 'request_body'})
LEGACY_RAW_KEY = 'shared_provider:v1:' + sha256((LegacyHoldingHttp.raw_cache_prefix + MASTER_URL).encode()).hexdigest()
LEGACY_ADMISSION_KEY = LegacyHoldingHttp._admission_key(MASTER_URL)


def is_shared(receipt):
    # A damaged new receipt cannot downgrade to a less expressive old schema.
    return isinstance(receipt, dict) and bool(_SHARED_MARKERS.intersection(receipt))


def _legacy_holding_cold_guard():
    from cache_store import get_cache_json
    for key in (LEGACY_RAW_KEY, LEGACY_ADMISSION_KEY):
        try:
            state = get_cache_json(key)
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        if state is None:
            continue
        if (not isinstance(state, dict)
                or key == LEGACY_ADMISSION_KEY and 'retry_at' not in state
                or state.get('error_kind') and 'retry_after_epoch' not in state and key == LEGACY_RAW_KEY
                or 'error_kind' in state and state['error_kind'] is not None
                   and (not isinstance(state['error_kind'], str) or not state['error_kind'])
                or 'fallback_eligible' in state and type(state['fallback_eligible']) is not bool
                or state.get('http_status') is not None
                   and (type(state['http_status']) is not int or not 100 <= state['http_status'] <= 599)):
            raise SourceResponseError('guard_storage_unavailable')
        for field in ('retry_at', 'retry_after_epoch', 'next_request_at'):
            until = state.get(field, 0)
            if not shared._number(until) or until < 0:
                raise SourceResponseError('guard_storage_unavailable')
            if until > time.time():
                # The old cache often kept only an exception class or lease.
                # It cannot justify a new request to either master endpoint.
                raise SourceResponseError('legacy_master_cooldown')


class _AnnualMasterHttp(IssuerMasterHttp):
    def __init__(self, deadline, *, legacy_holding=False):
        super().__init__(deadline)
        self.legacy_holding = legacy_holding

    def _guarded_download(self, url, diagnostic):
        if self.legacy_holding:
            _legacy_holding_cold_guard()
        return super()._guarded_download(url, diagnostic)


def request_master(http, *, legacy_holding=False):
    master = _AnnualMasterHttp(http.deadline, legacy_holding=legacy_holding)
    master.components = http.components
    try:
        return master.get_receipt(MASTER_URL)
    finally:
        if hasattr(http, 'http_request_count'):
            http.http_request_count += master.http_request_count


def read_master(receipt, legacy_reader, *, max_age=HISTORICAL_MAX_AGE):
    if not isinstance(receipt, dict) or receipt.get('source_url') not in (MASTER_URL, JSON_URL):
        raise ValueError('annual master URL invalid')
    if is_shared(receipt):
        return shared.original_bytes(receipt, max_age=max_age)
    return legacy_reader(receipt, receipt['source_url'])


def current_at(receipt, observed):
    if is_shared(receipt):
        return shared.live_or_historical_expiry_valid(receipt, shared.RAW_TTL, observed)
    stamp = receipt.get('retrieved_at')
    return (type(stamp) in (int, float) and math.isfinite(stamp)
            and 0 < stamp <= observed and observed - stamp < shared.RAW_TTL)


def body_audit(receipts, components):
    """Identity/index reuse is separate from acquiring financial statement bodies."""
    cached = any(r.get('cache_hit') is True for r in receipts)
    epoch = min(r['retrieved_at'] for r in receipts)
    sent = any(c.get('http_request_sent') is True for c in components)
    return {'cache_hit': cached, 'stale': False, 'fetched_at_epoch': epoch,
            'fetched_at': datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
            'event_kind': 'cache_hit' if cached else 'aggregate' if sent else 'local_block'}
