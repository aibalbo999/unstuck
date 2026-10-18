"""Shared official master acquisition, retaining the old news cold guards."""
from hashlib import sha256
import time

from search_provider_runtime import SourceResponseError
from . import official_issuer_master as shared
from .official_issuer_master_transport import IssuerMasterHttp


def _legacy_guard(url):
    from cache_store import get_cache_json
    # An opaque CSV failure cannot become permission to try JSON. Check the
    # JSON namespace too before a cold JSON request; never alter old expiry.
    urls = (shared.MASTER_URL, shared.JSON_URL) if url == shared.JSON_URL else (shared.MASTER_URL,)
    for endpoint in urls:
        key = 'shared_provider:v1:' + sha256(('issuer-news-raw:v1:' + endpoint).encode()).hexdigest()
        try:
            row = get_cache_json(key)
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        if row is None:
            continue
        if not isinstance(row, dict) or row.get('error_kind') and 'retry_after_epoch' not in row:
            raise SourceResponseError('guard_storage_unavailable')
        for field in ('retry_after_epoch', 'retry_at', 'next_request_at'):
            until = row.get(field, 0)
            if not shared._number(until) or until < 0:
                raise SourceResponseError('guard_storage_unavailable')
            if until > time.time():
                raise SourceResponseError('legacy_news_master_cooldown')


class RegisteredMasterHttp(IssuerMasterHttp):
    def _warm_fallback_guard(self):
        # Selecting a warm fallback must retain the primary news refusal that
        # would otherwise be checked before a new CSV request.
        _legacy_guard(shared.MASTER_URL)
        super()._warm_fallback_guard()

    def _guarded_download(self, url, diagnostic):
        _legacy_guard(url)
        return super()._guarded_download(url, diagnostic)


def request_master(http):
    master = RegisteredMasterHttp(http.deadline)
    master.components = http.components
    try:
        return master.get_receipt(shared.MASTER_URL)
    finally:
        http.http_request_count += master.http_request_count
