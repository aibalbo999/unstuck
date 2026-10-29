"""Observe the SDK's existing native session without replacing it or caches."""
import threading,time,re,inspect
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from urllib.parse import urlsplit,unquote,parse_qs
_LOCK=threading.Lock()
_GLOBAL_PROXY=ContextVar('yfinance_global_proxy_transport',default=None)


@contextmanager
def observe_global_proxy(symbol):
    """Bind one actual global-context SDK call; never borrow another operation."""
    from provider_correlation import current_correlation,current_source_identity
    binding=None
    try:
        from data_fetch.market_sources.global_context import TECH_PROXY_SYMBOLS,BROAD_PROXY_SYMBOLS
        allowed={row[0] for row in (*TECH_PROXY_SYMBOLS,*BROAD_PROXY_SYMBOLS)}
        context=current_correlation()
        if (isinstance(symbol,str) and symbol in allowed and context.get('ticker')
                and context.get('operation_id') and context.get('fetch_id')
                and current_source_identity()==('global_market_context','yfinance global context')):
            binding=(symbol,{key:context[key] for key in ('ticker','operation_id','fetch_id')})
    except Exception:
        pass
    token=_GLOBAL_PROXY.set(binding)
    try:
        if binding is not None:
            try:observe_yfinance()
            except Exception:pass
        yield
    finally:
        _GLOBAL_PROXY.reset(token)


def _record(method,url,params,response,started,stream):
    from provider_correlation import current_correlation,current_source_identity
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
    source='market_data';provider='yfinance native HTTP'
    message='Native Yahoo transport receipt only; parsed market data is separately audited.'
    binding=_GLOBAL_PROXY.get()
    if binding is not None:
        selected,owner=binding
        if (current_source_identity()!=('global_market_context','yfinance global context')
                or any(context.get(key)!=value for key,value in owner.items())
                or symbol!=selected or not request.path.startswith('/v8/finance/chart/')):return
        source='global_market_context';provider='yfinance global proxy native HTTP'
        message=f'Native Yahoo global proxy {selected} transport only; parsed global context is separately audited.'
    elif current_source_identity()==('global_market_context','yfinance global context'):
        return
    elif not isinstance(symbol,str)or symbol.upper()!=ticker.upper():return
    body=response.content
    if not isinstance(body,bytes):return
    record_source_audit_entries([{**context,'source':source,'provider':provider,
        'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
        'record_count':0,'status':'success'if response.status_code<400 else'error',
        'http_request_sent':True,'http_status':response.status_code,'response_bytes':len(body),
        'response_sha256':sha256(body).hexdigest(),'duration_ms':max(0,int((time.monotonic()-started)*1000)),
        'message':message}])


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
