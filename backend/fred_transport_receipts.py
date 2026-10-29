"""FRED transport evidence without API keys, query strings, or response bodies."""
from hashlib import sha256
from urllib.parse import urlsplit, parse_qs


def observe_response(response, *, series_id, native_call=False):
    try:
        import httpx, requests
        if not native_call or type(response) not in (httpx.Response, requests.Response):
            return
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        context = current_correlation()
        if not context.get('ticker') or not context.get('fetch_id') or series_id not in {'DGS10','CPIAUCSL','VIXCLS'}:
            return
        url = urlsplit(str(getattr(response, 'url', '')))
        if (url.scheme != 'https' or url.netloc != 'api.stlouisfed.org'
                or url.path != '/fred/series/observations' or url.fragment
                or parse_qs(url.query).get('series_id') != [series_id]
                or getattr(response, 'from_cache', False)):
            return
        code = getattr(response, 'status_code', None)
        body = response.content
        if type(code) is not int or not 100 <= code <= 599 or not isinstance(body, bytes) or len(body) > 2_000_000:
            return
        record_source_audit_entries([{**context,'source':'macro_indicators','provider':'FRED native HTTP',
            'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
            'record_count':0,'status':'success' if 200 <= code < 300 else 'error',
            'http_request_sent':True,'http_status':code,'response_bytes':len(body),
            'response_sha256':sha256(body).hexdigest(),
            'component_statuses':{series_id:{'series_id':series_id,'status':'transport_received',
                'http_status':code,'response_sha256':sha256(body).hexdigest()}},
            'message':'Native FRED transport only; parsed macro observations are separately audited.'}])
    except Exception:
        return
