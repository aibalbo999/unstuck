"""Receipts for the existing annual workforce/safety GET, never parsed success."""
from hashlib import sha256
import re


def observe_response(url, response, *, max_bytes):
    """Keep cache policy, source completeness and acquisition time unchanged."""
    try:
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
        status = getattr(response, 'status_code', None)
        body = response.content
        if (getattr(response, 'url', None) != url or getattr(response, 'from_cache', False)
                or type(status) is not int or not 100 <= status <= 599
                or not isinstance(body, bytes) or not 0 < len(body) <= max_bytes):
            return
        record_source_audit_entries([{**context, 'source': source,
            'provider': provider + ' native HTTP', 'event_kind': 'http_transport_receipt',
            'selection_policy': 'transport-receipt-only:v1', 'record_count': 0,
            'status': 'success' if 200 <= status < 300 else 'error',
            'http_request_sent': True, 'http_status': status,
            'response_bytes': len(body), 'response_sha256': sha256(body).hexdigest(),
            'message': 'Native annual disclosure GET only; issuer parsing and source completeness are separately audited.'}])
    except Exception:
        # Diagnostics must not change bytes, network exceptions, retries or TTL.
        return
