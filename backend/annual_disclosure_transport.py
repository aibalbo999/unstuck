"""Receipts for the existing annual workforce/safety GET, never parsed success."""
from hashlib import sha256
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar

_RECORD_RECEIPTS = ContextVar("annual_disclosure_receipts", default=True)


@contextmanager
def receipt_observation_scope(enabled):
    token = _RECORD_RECEIPTS.set(enabled is True)
    try:
        yield
    finally:
        _RECORD_RECEIPTS.reset(token)


def native_response(url, response):
    """Only this exact public GET may describe a new transport observation."""
    import httpx
    if type(response) is not httpx.Response:
        return False
    try:
        request = response.request
        return (request.method == 'GET' and request.url == url and response.url == url
            and not response.history and not getattr(response, 'from_cache', False)
            and not response.extensions.get('from_cache') and not response.extensions.get('cache_hit')
            and not any(key in request.headers for key in ('authorization', 'proxy-authorization', 'cookie'))
            and type(response.status_code) is int and 100 <= response.status_code <= 599)
    except RuntimeError:
        return False


def _complete_body(response, body):
    """httpx exposes decoded bytes; never label these as wire bytes."""
    if (response.status_code != 200 or not response.is_stream_consumed
            or not response.is_closed or response.headers.get("content-range")):
        return False
    if response.headers.get("content-encoding", "identity").lower() in {"", "identity"}:
        length = response.headers.get("content-length")
        if length is not None and (not length.isdecimal() or int(length) != len(body)):
            return False
    return True


def _archive_original(url, response, body, max_bytes):
    try:
        from official_response_evidence import archive_response
        proof = archive_response(body, source_url=url, retrieved_at=time.time(),
            evidence_kind="decoded_complete_http_response_body",
            http_status=response.status_code, max_bytes=max_bytes)
        if isinstance(proof, dict) and proof.get("status") == "archived":
            return {**proof, "request_method": "GET", "cache_hit": False,
                    "http_status_observed": True, "response_complete": True}
    except Exception:
        # Saving evidence must not turn a downloaded dataset into a retry.
        pass
    return None


def observe_response(url, response, *, max_bytes):
    """Keep cache policy, source completeness and acquisition time unchanged."""
    try:
        if not _RECORD_RECEIPTS.get():
            return
        import httpx
        if type(response) is not httpx.Response:
            return
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        from data_fetch.annual_workforce_provider import URLS, PROVIDER
        from data_fetch.annual_occupational_safety import URLS as SAFETY_URLS, PROVIDER as SAFETY_PROVIDER
        context = current_correlation()
        ticker = context.get('ticker')
        if (not isinstance(ticker, str) or not re.fullmatch(r'[0-9]{4,6}\.TW(?:O)?', ticker)
                or not context.get('fetch_id')):
            return
        suffix = '.TWO' if ticker.endswith('.TWO') else '.TW' if ticker.endswith('.TW') else None
        if suffix is None:
            return
        if url == URLS[suffix]:
            source, provider = 'annual_workforce', PROVIDER
        elif url == SAFETY_URLS[suffix]:
            source, provider = 'esg_occupational_safety', SAFETY_PROVIDER
        else:
            return
        if not native_response(url, response):
            return
        status = getattr(response, 'status_code', None)
        body = response.content
        if (getattr(response, 'url', None) != url or getattr(response, 'from_cache', False)
                or type(status) is not int or not 100 <= status <= 599
                or not isinstance(body, bytes) or not 0 < len(body) <= max_bytes):
            return
        complete = _complete_body(response, body)
        original = _archive_original(url, response, body, max_bytes) if complete else None
        entry = {**context, 'source': source,
            'provider': provider + ' native HTTP', 'event_kind': 'http_transport_receipt',
            'selection_policy': 'transport-receipt-only:v1', 'record_count': 0,
            'status': 'success' if 200 <= status < 300 else 'error',
            'http_request_sent': True, 'http_status': status,
            'http_status_observed': True, 'response_complete': complete, 'cache_hit': False,
            'response_bytes': len(body), 'response_sha256': sha256(body).hexdigest(),
            'message': 'Native annual disclosure GET only; issuer parsing and source completeness are separately audited.'}
        if original is not None:
            entry['raw_http_receipt'] = original
        record_source_audit_entries([entry])
    except Exception:
        # Diagnostics must not change bytes, network exceptions, retries or TTL.
        return
