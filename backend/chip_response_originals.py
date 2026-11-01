"""Passive original bytes from existing free chip responses; no requests."""
import time

PUBLIC_URLS = frozenset({
    'https://opendata.tdcc.com.tw/getOD.ashx?id=1-5',
    'https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?response=json',
})

def capture_chip_original(response, source_url):
    try:
        import httpx
        from provider_correlation import current_correlation, current_source_identity
        from official_response_evidence import archive_response
        context = current_correlation()
        if (source_url not in PUBLIC_URLS
                or current_source_identity() != ('chip_data', 'TDCC/TWSE/TPEx chip data')
                or any(not context.get(k) for k in ('ticker', 'fetch_id', 'operation_id'))
                or type(response) is not httpx.Response or response.status_code != 200
                or response.history or str(response.url) != source_url
                or str(response.request.url) != source_url or response.request.method != 'GET'
                or getattr(response, 'from_cache', False) or response.extensions.get('from_cache') is True
                or any(response.request.headers.get(k) for k in ('authorization', 'cookie', 'proxy-authorization'))):
            return None
        body = response.content
        if not isinstance(body, bytes) or not 0 < len(body) <= 8_000_000:
            return None
        proof = archive_response(body, source_url=source_url, retrieved_at=time.time(),
                                 evidence_kind='decoded_complete_http_response_body', max_bytes=8_000_000)
        if proof.get('status') != 'archived':
            return None
        return {**proof, 'http_status_observed': True, 'response_complete': True, 'cache_hit': False}
    except Exception:
        return None
