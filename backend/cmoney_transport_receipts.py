"""Observe completed existing native forum GETs, never admitted discussion data."""
from hashlib import sha256
import json
import re

MARKER = b'\nSTOCK_AGENT_CURL_META:'


def observe_download(url, parts, returncode, error, *, max_bytes):
    """Fail closed on missing/mismatched curl metadata; leave acquisition unchanged."""
    try:
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        context = current_correlation()
        ticker = context.get('ticker')
        if (not isinstance(ticker, str) or not re.fullmatch(r'[0-9]{4}\.TW(?:O)?', ticker)
                or not context.get('fetch_id') or parts.get('process_started') is not True
                or error is not None or type(returncode) is not int or returncode not in (0, 22)):
            return
        stock_id = ticker.split('.')[0]
        if url == f'https://www.cmoney.tw/finance/{stock_id}/f00025':
            component = 'finance_listing'
        elif url == f'https://forum-web.cmoney.tw/stocks/{stock_id}':
            component = 'stock_listing'
        elif isinstance(url, str) and re.fullmatch(r'https://www\.cmoney\.tw/forum/article/[0-9]{6,12}', url):
            component = 'original_article'
        else:
            return
        raw = parts.get('body')
        metadata = parts.get('metadata')
        headers = parts.get('headers')
        if (not isinstance(raw, bytes) or len(raw) > max_bytes
                or not isinstance(metadata, bytes) or metadata.count(MARKER) != 1
                or not isinstance(headers, bytes)):
            return
        meta = json.loads(metadata.split(MARKER)[1])
        codes = re.findall(rb'^HTTP/\S+ +([1-5][0-9]{2})(?: [^\r\n]*)?\r?\n', headers, re.M)
        if not isinstance(meta, dict) or not codes:
            return
        code = meta.get('http_code')
        size = meta.get('size_download')
        if (type(code) is not int or code != int(codes[-1])
                or not 100 <= code <= 599 or meta.get('url_effective') != url
                or type(meta.get('num_redirects')) is not int or meta['num_redirects'] != 0
                or type(size) not in (int, float) or size != len(raw)
                or returncode == 22 and code < 400):
            return
        digest = sha256(raw).hexdigest()
        record_source_audit_entries([{**context, 'source': 'social_sentiment',
            'provider': 'CMoney native HTTP', 'event_kind': 'http_transport_receipt',
            'selection_policy': 'transport-receipt-only:v1', 'record_count': 0,
            'status': 'success' if 200 <= code < 300 else 'error',
            'http_request_sent': True, 'http_status': code,
            'response_bytes': len(raw), 'response_sha256': digest,
            'component_statuses': {component: {'status': 'transport_received',
                'http_status': code, 'response_bytes': len(raw), 'response_sha256': digest}},
            'message': 'Existing completed native GET only; company identity, date and original post parsing are separately audited.'}])
    except Exception:
        # Receipts cannot change returned bytes, failures, retries, or freshness.
        return
