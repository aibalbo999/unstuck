"""TCFHC QA identity fallback; the shared legacy body transport stays unchanged."""
import time
from search_provider_runtime import SourceResponseError
from . import conference_issuer_master as master_identity
from .tcfhc_conference_transport import (
    ConferenceHttp as _ConferenceHttp, MASTER_URL, RAW_TTL,
    original_bytes as _original_bytes, valid_epoch,
)


def _legacy_original_bytes(receipt, url, *, max_age=86400):
    raw = _original_bytes(receipt, url, max_age=max_age)
    if not valid_epoch(receipt['retrieved_at'], max_age):
        raise ValueError('TCFHC original expired during archive readback')
    return raw


def original_bytes(receipt, url, *, max_age=86400):
    if url in (MASTER_URL, master_identity.JSON_URL):
        return master_identity.read_master(receipt, url, _legacy_original_bytes, max_age=max_age)
    return _legacy_original_bytes(receipt, url, max_age=max_age)


class ConferenceHttp(_ConferenceHttp):
    # Inherit both legacy cache/guard namespaces. No new path around cooldown.
    def read_original(self, receipt, url, *, max_age):
        return original_bytes(receipt, url, max_age=max_age)

    def get_receipt(self, url):
        if url == MASTER_URL:
            return master_identity.request_master(self)
        raw, receipt = super().get_receipt(url)
        if not valid_epoch(receipt['retrieved_at'], RAW_TTL):
            raise SourceResponseError('original_expired')
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw, receipt
