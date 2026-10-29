"""Observe the SDK's existing native session without replacing it or caches."""
import threading,time,re,inspect
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from urllib.parse import urlsplit,unquote,parse_qs
_LOCK=threading.Lock()
_GLOBAL_PROXY=ContextVar('yfinance_global_proxy_transport',default=None)
_ANNUAL=ContextVar('yfinance_annual_statement_transport',default=None)
_PEER=ContextVar('yfinance_selected_peer_transport',default=None)


@contextmanager
def observe_peer_metrics(symbol):
    """One selected peer quote belongs to its root source operation, not itself."""
    from provider_correlation import current_correlation,current_source_identity
    context=current_correlation();binding=None
    if (isinstance(symbol,str) and re.fullmatch(r'[A-Z0-9][A-Z0-9.^=-]{0,39}',symbol)
            and symbol!=context.get('ticker') and all(context.get(k)for k in('ticker','fetch_id','operation_id'))
            and current_source_identity()==('dynamic_peer_metrics','FinMind/yfinance')
            and _GLOBAL_PROXY.get() is None and _ANNUAL.get() is None):
        binding=(symbol,{k:context[k]for k in('ticker','fetch_id','operation_id')})
    token=_PEER.set(binding)
    try:
        if binding is not None:
            try:observe_yfinance()
            except Exception:pass
        yield
    finally:
        _PEER.reset(token)


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


@contextmanager
def observe_annual_statements(ticker, metadata):
    """Observe only a bounded existing annual SDK read, preserving its caches."""
    from provider_correlation import current_correlation, correlation_scope
    context = current_correlation()
    binding = None
    if (isinstance(metadata, dict) and isinstance(ticker, str)
            and context.get('ticker') == ticker == metadata.get('ticker')
            and context.get('fetch_id') and context['fetch_id'] == metadata.get('fetch_id')
            and metadata.get('operation_id') and _GLOBAL_PROXY.get() is None and _PEER.get() is None):
        binding = {key: metadata[key] for key in ('ticker', 'fetch_id', 'operation_id')}
    token = _ANNUAL.set(binding)
    try:
        if binding is None:
            yield
        else:
            try:
                observe_yfinance()
            except Exception:
                pass
            with correlation_scope(**binding):
                yield
    finally:
        _ANNUAL.reset(token)


def _annual_symbol(request, actual, params, binding, context):
    if any(context.get(key) != value for key, value in binding.items()):
        return None
    match = re.fullmatch(r'/ws/fundamentals-timeseries/v1/finance/timeseries/([^/]+)', request.path)
    if match is None or unquote(match[1]) != binding['ticker']:
        return None
    query = parse_qs(request.query)
    actual_query = parse_qs(actual.query)
    supplied = params if isinstance(params, dict) else {}
    def values(key):
        original = query.get(key)
        if original is None and key in supplied:
            raw = supplied[key]
            original = [raw] if isinstance(raw, str) else raw
        final = actual_query.get(key, original)
        return original if original == final else None
    if values('symbol') != [binding['ticker']]:
        return None
    types = values('type')
    if not isinstance(types, list) or len(types) != 1 or not isinstance(types[0], str):
        return None
    from yfinance.const import fundamentals_keys
    allowed = {'annual' + value for fields in fundamentals_keys.values() for value in fields}
    fields = types[0].split(',')
    return binding['ticker'] if fields and all(field in allowed for field in fields) else None


def _record(method,url,params,response,started,stream):
    from provider_correlation import current_correlation,current_source_identity
    from provider_sla import record_source_audit_entries
    context=current_correlation();ticker=context.get('ticker','')
    if method!='GET' or not ticker or stream:return
    request=urlsplit(url);actual=urlsplit(response.url)
    if (request.scheme!='https' or actual.scheme!='https' or request.hostname not in {'query1.finance.yahoo.com','query2.finance.yahoo.com'}
        or actual.hostname!=request.hostname or actual.path!=request.path or request.username or request.password
        or request.port not in (None,443) or getattr(response,'from_cache',False)):return
    annual_binding = _ANNUAL.get()
    if annual_binding is not None:
        symbol = _annual_symbol(request, actual, params, annual_binding, context)
        if symbol is None:
            return
        body = response.content
        if not isinstance(body, bytes):
            return
        record_source_audit_entries([{**context, 'source': 'financial_statements',
            'provider': 'yfinance annual statements native HTTP',
            'event_kind': 'http_transport_receipt', 'selection_policy': 'transport-receipt-only:v1',
            'record_count': 0, 'status': 'success' if 200 <= response.status_code < 300 else 'error',
            'http_request_sent': True, 'http_status': response.status_code,
            'response_bytes': len(body), 'response_sha256': sha256(body).hexdigest(),
            'duration_ms': max(0, int((time.monotonic() - started) * 1000)),
            'message': 'Native Yahoo annual transport only; parsed statements and SDK cache remain separately audited.'}])
        return
    match=re.fullmatch(r'/v(?:8/finance/chart|10/finance/quoteSummary)/([^/]+)',request.path)
    if match is not None:symbol=unquote(match[1])
    elif request.path=='/v7/finance/quote':
        values=parse_qs(actual.query).get('symbols',[])
        symbol=values[0]if len(values)==1 else(params or{}).get('symbols','')
    else:return
    source='market_data';provider='yfinance native HTTP'
    message='Native Yahoo transport receipt only; parsed market data is separately audited.'
    peer_binding=_PEER.get()
    if peer_binding is not None:
        selected,owner=peer_binding
        # Identity-bearing query fields cannot contradict a selected path symbol.
        for query in (parse_qs(request.query,keep_blank_values=True),
                      parse_qs(actual.query,keep_blank_values=True),params if isinstance(params,dict) else {}):
            for key in ('symbol','symbols'):
                if key in query:
                    values=query[key]
                    if ([values] if isinstance(values,str) else values)!=[selected]:return
        if (current_source_identity()!=('dynamic_peer_metrics','FinMind/yfinance')
                or any(context.get(key)!=value for key,value in owner.items())
                or symbol!=selected or not (request.path.startswith('/v10/finance/quoteSummary/')
                                            or request.path=='/v7/finance/quote')):return
        body=response.content;code=response.status_code
        if not isinstance(body,bytes) or type(code)is not int or not 100<=code<=599:return
        digest=sha256(body).hexdigest()
        record_source_audit_entries([{**context,'source':'dynamic_peer_metrics',
            'provider':'yfinance peer native HTTP','event_kind':'http_transport_receipt',
            'selection_policy':'transport-receipt-only:v1','record_count':0,
            'status':'success' if 200<=code<300 else 'error','peer_symbol':selected,
            'http_request_sent':True,'http_status':code,'response_bytes':len(body),
            'response_sha256':digest,'duration_ms':max(0,int((time.monotonic()-started)*1000)),
            'component_statuses':{selected:{'status':'transport_received','http_status':code,
                                           'response_sha256':digest}},
            'message':'Native selected-peer quote transport only; peer identity, comparability and parsed metrics remain separately checked.'}])
        return
    elif (current_source_identity() or (None,))[0]=='dynamic_peer_metrics':
        return
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
