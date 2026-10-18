"""Shared complete issuer identity, retaining each conference's old cold guards."""
from hashlib import sha256
import csv
import io
import time

from search_provider_runtime import SourceResponseError
from . import official_issuer_master as shared
from .official_issuer_master_transport import IssuerMasterHttp
from .official_issuer_master_json import parse_rows

MASTER_URL = shared.MASTER_URL
JSON_URL = shared.JSON_URL
_SHARED_MARKERS = frozenset({'retrieval_policy', 'response_metadata', 'acquisition_manifest',
                             'wire_original', 'fresh_until_epoch', 'reusable', 'request_body'})


def is_shared(receipt):
    return isinstance(receipt, dict) and bool(_SHARED_MARKERS.intersection(receipt))



def valid_master_policy(proof_policy, receipt, policy, legacy_policy):
    """New proof requires its full typed master; old proof is CSV-only replay."""
    if not isinstance(receipt, dict):
        return False
    if proof_policy == policy:
        return is_shared(receipt) and receipt.get('source_url') in (MASTER_URL, JSON_URL)
    return (proof_policy == legacy_policy and not is_shared(receipt)
            and receipt.get('source_url') == MASTER_URL)


def _legacy_cold_guard(raw_prefix, admission_prefix):
    from cache_store import get_cache_json
    raw_key = 'shared_provider:v1:' + sha256((raw_prefix + MASTER_URL).encode()).hexdigest()
    admission_key = admission_prefix + sha256(MASTER_URL.encode()).hexdigest()
    for key in (raw_key, admission_key):
        try:
            state = get_cache_json(key)
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        if state is None:
            continue
        if (not isinstance(state, dict)
                or key == admission_key and 'retry_at' not in state
                or key == raw_key and state.get('error_kind') and 'retry_after_epoch' not in state
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
                # Opaque old leases/errors cannot authorize either new endpoint.
                raise SourceResponseError('legacy_master_cooldown')


class _ConferenceMasterHttp(IssuerMasterHttp):
    def __init__(self, deadline, raw_prefix, admission_prefix):
        super().__init__(deadline)
        self.legacy_prefixes = (raw_prefix, admission_prefix)

    def _guarded_download(self, url, diagnostic):
        _legacy_cold_guard(*self.legacy_prefixes)
        return super()._guarded_download(url, diagnostic)


def request_master(http):
    master = _ConferenceMasterHttp(http.deadline, http.raw_cache_prefix, http.admission_prefix)
    master.components = http.components
    try:
        return master.get_receipt(MASTER_URL)
    finally:
        http.http_request_count += master.http_request_count


def read_master(receipt, url, legacy_reader, *, max_age):
    if not isinstance(receipt, dict) or url not in (MASTER_URL, JSON_URL) or receipt.get('source_url') != url:
        raise ValueError('Conference master URL invalid')
    if is_shared(receipt):
        return shared.original_bytes(receipt, max_age=max_age)
    if url != MASTER_URL:
        raise ValueError('Legacy conference master must be CSV')
    return legacy_reader(receipt, url, max_age=max_age)


def current_at(receipt, max_age, observed):
    if is_shared(receipt):
        return shared.live_or_historical_expiry_valid(receipt, max_age, observed)
    stamp = receipt.get('retrieved_at')
    return shared._number(stamp) and 0 < stamp <= observed and observed - stamp < max_age


_NO_EPOCH = object()


def reference_epoch(epoch=_NO_EPOCH, *, as_of_epoch=None):
    """Explicit archive replay changes date-age only; never renews original time."""
    now = time.time()
    observed = now if as_of_epoch is None else as_of_epoch
    if (not shared._number(observed) or not 0 < observed <= now
            or epoch is not _NO_EPOCH and (not shared._number(epoch) or not 0 < epoch <= observed)):
        raise ValueError('Conference reference epoch invalid')
    return observed


def master_rows(raw, epoch, url):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Conference master size invalid')
    if url == JSON_URL:
        return parse_rows(raw, epoch)
    if url != MASTER_URL:
        raise ValueError('Conference master URL invalid')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
        rows = list(reader); fields = reader.fieldnames
    except csv.Error as exc:
        raise ValueError('Conference master CSV malformed') from exc
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('Conference complete master shape invalid')
    return rows
