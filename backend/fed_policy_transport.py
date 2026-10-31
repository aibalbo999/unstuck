"""One normal bounded official feed read; raw-cache replay is never native HTTP."""
from datetime import datetime, timezone
from hashlib import sha256
import time
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
from search_provider_runtime import SourceResponseError
from fed_policy_metadata import FEED_URL, parse_policy_feed

class PolicyHttp(IssuerNewsHttp):
    @staticmethod
    def route_contract(url):
        if url != FEED_URL:
            raise SourceResponseError('transport_url_invalid')
        return 1_000_000, {'text/xml', 'application/xml', 'application/rss+xml'}

def _record_transport(component, *, raw=None, error=None):
    if component.get('http_request_sent') is not True or component.get('cache_hit') is True:
        return
    try:
        from provider_correlation import current_correlation, current_source_identity
        from provider_sla import record_source_audit_entries
        ctx = current_correlation()
        if (current_source_identity() != ('international_news_context', 'GDELT / Google News RSS')
                or not all(ctx.get(k) for k in ('ticker', 'fetch_id', 'operation_id'))):
            return
        details = {}
        if raw is not None:
            details.update(http_status=200, response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        elif type(getattr(error, 'status_code', None)) is int:
            details['http_status'] = error.status_code
        if error is not None:
            details['error_kind'] = getattr(error, 'error_kind', 'transport_error')
        record_source_audit_entries([{**ctx, **details, 'source': 'international_news_context',
            'provider': 'Federal Reserve monetary-policy native HTTP',
            'status': 'success' if raw is not None else 'error', 'record_count': 0,
            'event_kind': 'http_transport_receipt', 'selection_policy': 'transport-receipt-only:v1',
            'http_request_sent': True, 'cache_hit': False,
            'message': 'Official policy feed transport only; parsed metadata is separately qualified.'}])
    except Exception:
        pass

def load_policy_feed():
    client = PolicyHttp(time.monotonic() + 5.)
    try:
        raw = client.get(FEED_URL)
    except Exception as exc:
        if client.components:
            _record_transport(client.components[-1], error=exc)
        raise
    component = dict(client.components[-1])
    # get() validates the exact URL, complete 200 response and raw hash before return.
    _record_transport(component, raw=raw)
    return {'raw': raw, 'cache_hit': component.get('cache_hit') is True,
            'fetched_at_epoch': component.get('fetched_at_epoch')}

def policy_topics(payload, *, tag, lookback_days):
    return parse_policy_feed(payload['raw'], tag=tag, now=datetime.now(timezone.utc), lookback_days=lookback_days)
