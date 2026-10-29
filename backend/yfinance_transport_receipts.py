"""Observe the SDK's existing native session without replacing it or caches."""
import threading,time,re,inspect
from hashlib import sha256
from urllib.parse import urlsplit,unquote,parse_qs
_LOCK=threading.Lock()


def _record(method,url,params,response,started,stream):
    from provider_correlation import current_correlation
    from provider_sla import record_source_audit_entries
    context=current_correlation();ticker=context.get('ticker','')
    if method!='GET' or not ticker or stream:return
    request=urlsplit(url);actual=urlsplit(response.url)
    if (request.scheme!='https' or actual.scheme!='https' or request.hostname not in {'query1.finance.yahoo.com','query2.finance.yahoo.com'}
        or actual.hostname!=request.hostname or actual.path!=request.path or request.username or request.password
        or request.port not in (None,443) or getattr(response,'from_cache',False)):return
    match=re.fullmatch(r'/v(?:8/finance/chart|10/finance/quoteSummary)/([^/]+)',request.path)
    if match is not None:symbol=unquote(match[1])
    elif request.path=='/v7/finance/quote':
        values=parse_qs(actual.query).get('symbols',[])
        symbol=values[0]if len(values)==1 else(params or{}).get('symbols','')
    else:return
    if not isinstance(symbol,str)or symbol.upper()!=ticker.upper():return
    body=response.content
    if not isinstance(body,bytes):return
    record_source_audit_entries([{**context,'source':'market_data','provider':'yfinance native HTTP',
        'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
        'record_count':0,'status':'success'if response.status_code<400 else'error',
        'http_request_sent':True,'http_status':response.status_code,'response_bytes':len(body),
        'response_sha256':sha256(body).hexdigest(),'duration_ms':max(0,int((time.monotonic()-started)*1000)),
        'message':'Native Yahoo transport receipt only; parsed market data is separately audited.'}])


def observe_session(session):
    from curl_cffi.requests import Session
    if type(session)is not Session:return False
    with _LOCK:
        if getattr(session,'_stock_transport_observed',False):return True
        original=session._request_once
        if getattr(original,'__func__',None)is not Session._request_once:return False
        signature=inspect.signature(original)
        def observed(*args,**kwargs):
            started=time.monotonic();response=original(*args,**kwargs)
            try:
                bound=signature.bind_partial(*args,**kwargs).arguments
                values={**bound,**bound.get('kwargs',{}),**bound.get('kw',{})}
                _record(values.get('method',''),values.get('url',''),values.get('params'),response,started,values.get('stream',False))
            except Exception:pass
            return response
        session._request_once=observed;session._stock_transport_observed=True
    return True


def observe_yfinance():
    try:
        from yfinance.data import YfData
        return observe_session(YfData(session=None)._session)
    except Exception:return False
