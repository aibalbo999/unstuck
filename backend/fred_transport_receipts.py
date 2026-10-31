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


def observe_parsed_response(response, *, series_id, observations, native_call=False):
    """Diagnostic only: original bytes and existing parser, never a success row."""
    try:
        import httpx, requests
        from macro_fetcher import _parse_observation
        from provider_correlation import current_correlation
        from provider_sla import record_source_audit_entries
        if not native_call or type(response) not in (httpx.Response, requests.Response):
            return
        ctx = current_correlation()
        if not all(ctx.get(k) for k in ('ticker', 'fetch_id', 'operation_id')):
            return
        url = urlsplit(str(response.url))
        if (series_id not in {'DGS10','CPIAUCSL','VIXCLS'} or url.scheme != 'https'
                or url.netloc != 'api.stlouisfed.org' or url.path != '/fred/series/observations'
                or url.fragment or parse_qs(url.query).get('series_id') != [series_id]
                or getattr(response, 'from_cache', False) or response.status_code != 200):
            return
        body = response.content
        if not isinstance(body, bytes) or not 0 < len(body) <= 2_000_000:
            return
        payload = response.json()
        if (not isinstance(payload, dict) or not isinstance(observations, list)
                or payload.get('observations') != observations):
            return
        from fred_public_original import archive_public_response
        original = archive_public_response(response, series_id=series_id, payload=payload)
        usable = sum(isinstance(row, dict) and _parse_observation(row) is not None for row in observations)
        record_source_audit_entries([{**ctx, 'source':'macro_indicators',
            'provider':'FRED parsed observations', 'status':'success', 'record_count':0,
            'event_kind':'http_parsed_receipt', 'selection_policy':'parsed-receipt-only:v1',
            'http_request_sent':True, 'http_status':200, 'response_bytes':len(body),
            'response_sha256':sha256(body).hexdigest(),
            'raw_count':len(observations), 'usable_count':usable, 'raw_http_receipt':original,
            'component_statuses':{series_id:{'series_id':series_id,'status':'parsed',
                'response_sha256':sha256(body).hexdigest()}},
            'message':'Diagnostic parser linkage only; not a separate acquisition or freshness qualification.'}])
    except Exception:
        return
