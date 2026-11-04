"""Originals for existing exact anonymous FX GETs; never parsed quote success."""
from hashlib import sha256
import time
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlsplit, parse_qs

_RECORD_RECEIPTS = ContextVar("fx_receipt_observation", default=True)
MAX_BYTES = 2_000_000


@contextmanager
def receipt_observation_scope(enabled):
    token = _RECORD_RECEIPTS.set(enabled is True)
    try:
        yield
    finally:
        _RECORD_RECEIPTS.reset(token)


def _complete_body(response, body):
    if (response.status_code == 206 or not response.is_stream_consumed
            or not response.is_closed or response.headers.get("content-range")):
        return False
    # httpx.content is decoded, so compressed transfer length is not its size.
    if response.headers.get("content-encoding", "identity").lower() in {"", "identity"}:
        length = response.headers.get("content-length")
        if length is not None and (not length.isdecimal() or int(length) != len(body)):
            return False
    return True


def _archive_original(response, url, body):
    try:
        from official_response_evidence import archive_response
        proof = archive_response(body, source_url=url, retrieved_at=time.time(),
            evidence_kind="decoded_complete_http_response_body",
            http_status=response.status_code, max_bytes=MAX_BYTES)
        if isinstance(proof, dict) and proof.get("status") == "archived":
            return {**proof, "request_method": "GET", "cache_hit": False,
                    "http_status_observed": True, "response_complete": True}
    except Exception:
        # Diagnostics cannot discard data or cause another bank request.
        pass
    return None

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
        if not _RECORD_RECEIPTS.get():
            return
        import httpx
        from provider_correlation import current_correlation,current_source_identity
        from provider_sla import record_source_audit_entries
        context=current_correlation()
        if (native_call is not True or type(response)is not httpx.Response
                or current_source_identity()!=OWNER
                or not all(context.get(k)for k in('ticker','fetch_id','operation_id'))
                or getattr(response,'from_cache',False) or response.history
                or response.extensions.get('from_cache') or response.extensions.get('cache_hit')
                or any(k in response.request.headers for k in ('authorization','proxy-authorization','cookie'))):return
        original=urlsplit(request_url);actual=urlsplit(str(response.url))
        endpoint=ENDPOINTS.get((original.hostname,original.path))
        if (endpoint is None or original.scheme!='https' or original.username or original.password
                or original.port not in(None,443) or original.fragment
                or actual!=original or str(response.request.url)!=str(response.url)
                or response.request.method!='GET' or parse_qs(original.query,keep_blank_values=True)!=endpoint[0]):return
        body=response.content;code=response.status_code
        if not isinstance(body,bytes) or len(body)>MAX_BYTES or type(code)is not int or not 100<=code<=599:return
        digest=sha256(body).hexdigest()
        complete = _complete_body(response, body)
        original_receipt = _archive_original(response, request_url, body) if complete and code == 200 and body else None
        entry = {**context,'source':'taiwan_open_data','provider':endpoint[1],
            'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
            'record_count':0,'status':'success' if 200<=code<300 else 'error',
            'http_request_sent':True,'http_status':code,'response_bytes':len(body),'response_sha256':digest,
            'http_status_observed':True,'response_complete':complete,'cache_hit':False,
            'component_statuses':{original.hostname+original.path:{'status':'transport_received',
                'http_status':code,'response_sha256':digest}},
            'message':'Native FX transport only; parsed currency, quote date, quote kind and shared cache are separately checked.'}
        if original_receipt is not None:
            entry['raw_http_receipt'] = original_receipt
        record_source_audit_entries([entry])
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
