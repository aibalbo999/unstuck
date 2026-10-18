"""Master-only acquisition surface with explicit legacy Winbond compatibility.

The native GET implementation is reused, not its issuer routes or cache. Only
these two complete official master URLs may reach that implementation.
"""
from hashlib import sha256
from types import SimpleNamespace
import time

from search_provider_runtime import SourceResponseError
from . import official_issuer_master as shared
from . import gce_conference_transport as native
from . import winbond_conference_transport as legacy

MASTER_URL = shared.MASTER_URL
JSON_URL = shared.JSON_URL
LEGACY_RAW_KEY = 'shared_provider:v1:' + sha256((legacy.ConferenceHttp.raw_cache_prefix + MASTER_URL).encode()).hexdigest()
LEGACY_ADMISSION_KEY = legacy.ConferenceHttp._admission_key(MASTER_URL)


def _legacy_cold_guard(*, json_fallback=False):
    """A changed cache namespace is not permission to bypass an old failure.

Unknown legacy SourceResponseError rows lose their original cause, so they
cannot authorize JSON. Warm shared originals are checked before this guard.
    """
    from cache_store import get_cache_json
    blocked = None
    for key in (LEGACY_RAW_KEY, LEGACY_ADMISSION_KEY):
        try:
            state = get_cache_json(key)
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        if state is None:
            continue
        if (not isinstance(state, dict)
                or key == LEGACY_ADMISSION_KEY and 'retry_at' not in state
                or key == LEGACY_RAW_KEY and state.get('error_kind') and 'retry_after_epoch' not in state
                or 'fallback_eligible' in state and type(state['fallback_eligible']) is not bool):
            raise SourceResponseError('guard_storage_unavailable')
        for field in ('retry_at', 'retry_after_epoch', 'next_request_at'):
            until = state.get(field, 0)
            if not shared._number(until) or until < 0:
                raise SourceResponseError('guard_storage_unavailable')
            if until <= time.time():
                continue
            kind = state.get('error_kind')
            status = state.get('http_status')
            if (status is not None and (type(status) is not int or not 100 <= status <= 599)
                    or state.get('fallback_eligible') is False):
                raise SourceResponseError('guard_storage_unavailable')
            if status in (401, 403, 429):
                raise SourceResponseError({401:'authentication',403:'access_denied',429:'rate_limited'}[status],status_code=status)
            if not isinstance(kind,str) or kind not in shared.FALLBACK_ERRORS:
                # Bare leases and exception-class-only failures are opaque.
                raise SourceResponseError(kind if isinstance(kind,str) and kind != 'SourceResponseError' else 'guard_storage_unavailable')
            if field == 'next_request_at':
                blocked = 'request_pacing'
            elif blocked is None:
                blocked = 'cooldown'
    if blocked and not (json_fallback and blocked == 'cooldown'):
        raise SourceResponseError(blocked)


class IssuerMasterHttp:
    def __init__(self, deadline, *, force_refresh=False, use_cache=True):
        self.deadline = deadline
        self.components = []
        self.http_request_count = 0
        # Shared identity freshness is independent of issuer-body refresh.

    def _check(self):
        shared._check(self.deadline)

    def _external_guards(self, url):
        return native.ConferenceHttp._external_guards(self, url)

    def download_original(self, url, diagnostic):
        if url not in (MASTER_URL, JSON_URL):
            raise SourceResponseError('transport_url_invalid')
        return native.ConferenceHttp.download_original(self, url, diagnostic)

    def _guarded_download(self, url, diagnostic):
        self._check()
        if url == MASTER_URL:
            _legacy_cold_guard()
        elif url == JSON_URL:
            # Shared CSV cooldown may skip its download callback entirely.
            # Recheck terminal legacy failures before a cold fallback too.
            _legacy_cold_guard(json_fallback=True)
        else:
            raise SourceResponseError('transport_url_invalid')
        self._check()
        return self.download_original(url, diagnostic)

    def _warm_fallback_guard(self):
        _legacy_cold_guard(json_fallback=True)

    def get_receipt(self, url):
        if url != MASTER_URL:
            raise SourceResponseError('transport_url_invalid')
        # Some issuer transports delegate this method without inheriting us.
        guard = getattr(self, '_warm_fallback_guard',
                        lambda: _legacy_cold_guard(json_fallback=True))
        return shared.request_master(SimpleNamespace(deadline=self.deadline,
            components=self.components, download_original=self._guarded_download,
            warm_fallback_guard=guard))


def original_bytes(receipt, url, *, max_age=shared.RAW_TTL):
    if url not in (MASTER_URL, JSON_URL) or not isinstance(receipt,dict) or receipt.get('source_url') != url:
        raise ValueError('master original URL mismatch')
    if 'retrieval_policy' in receipt:
        return shared.original_bytes(receipt, max_age=max_age)
    if url != MASTER_URL:
        raise ValueError('legacy master must be CSV')
    # Preserve the exact old receipt and its independently retained cache TTL.
    return legacy.original_bytes(receipt, url, max_age=max_age)
