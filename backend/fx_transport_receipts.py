"""Exact native FX responses only; no stored body, guessed calls or cached success."""
from hashlib import sha256
from urllib.parse import urlsplit, parse_qs

# Existing normal provider paths only. No additional request or provider fallback.
ENDPOINTS={
    ('rate.bot.com.tw','/xrt/flcsv/0/day'):({},'Bank of Taiwan native HTTP'),
    ('www.megabank.com.tw','/api/client/ExchangeRate/GetRateData'):
        ({'sc_lang':['zh-TW'],'sc_site':['bank-zh-tw'],'dic_lang':['zh-TW']},'Mega Bank native HTTP'),
    ('www.megabank.com.tw','/api/client/ExchangeRate/GetCurrenciesData'):
        ({'sc_lang':['zh-TW'],'sc_site':['bank-zh-tw'],'dic_lang':['zh-TW']},'Mega Bank native HTTP'),
    ('open.er-api.com','/v6/latest/USD'):({},'open.er-api.com native HTTP'),
    ('fred.stlouisfed.org','/graph/fredgraph.csv'):({'id':['DEXTAUS']},'FRED DEXTAUS native HTTP'),
}
OWNER=('taiwan_open_data','Taiwan Open Data (Exchange Rates)')


def observe_response(response, *, request_url, native_call=False):
    try:
        import httpx
        from provider_correlation import current_correlation,current_source_identity
        from provider_sla import record_source_audit_entries
        context=current_correlation()
        if (native_call is not True or type(response)is not httpx.Response
                or current_source_identity()!=OWNER
                or not all(context.get(k)for k in('ticker','fetch_id','operation_id'))
                or getattr(response,'from_cache',False) or response.history):return
        original=urlsplit(request_url);actual=urlsplit(str(response.url))
        endpoint=ENDPOINTS.get((original.hostname,original.path))
        if (endpoint is None or original.scheme!='https' or original.username or original.password
                or original.port not in(None,443) or original.fragment
                or actual!=original or str(response.request.url)!=str(response.url)
                or response.request.method!='GET' or parse_qs(original.query,keep_blank_values=True)!=endpoint[0]):return
        body=response.content;code=response.status_code
        if not isinstance(body,bytes) or len(body)>2_000_000 or type(code)is not int or not 100<=code<=599:return
        digest=sha256(body).hexdigest()
        record_source_audit_entries([{**context,'source':'taiwan_open_data','provider':endpoint[1],
            'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
            'record_count':0,'status':'success' if 200<=code<300 else 'error',
            'http_request_sent':True,'http_status':code,'response_bytes':len(body),'response_sha256':digest,
            'component_statuses':{original.hostname+original.path:{'status':'transport_received',
                'http_status':code,'response_sha256':digest}},
            'message':'Native FX transport only; parsed currency, quote date, quote kind and shared cache are separately checked.'}])
    except Exception:
        # Transport/audit observation never changes the provider response or error.
        return


def native_get(fetcher, url, **kwargs):
    """Observe one existing GET, including its original HTTPStatusError response."""
    import httpx
    try:
        response=fetcher(url, **kwargs)
    except httpx.HTTPStatusError as exc:
        observe_response(exc.response, request_url=url, native_call=True)
        raise
    observe_response(response, request_url=url, native_call=True)
    return response
