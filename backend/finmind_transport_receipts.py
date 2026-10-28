"""Observe one SDK-owned Session; never modify SDK/global requests or data."""
from hashlib import sha256
from urllib.parse import urlsplit,parse_qs
import time
import threading

_LOCK=threading.Lock()
_DATASETS={'TaiwanStockMonthRevenue':'monthly_revenue',
 'TaiwanStockInstitutionalInvestorsBuySell':'institutional_trading',
 'TaiwanStockNews':'recent_catalysts','TaiwanStockPER':'pe_river_chart',
 'TaiwanStockFinancialStatements':'financial_statements'}


def _record(session,request,response,started):
    import requests
    from provider_correlation import current_correlation
    from provider_sla import record_source_audit_entries
    parts=urlsplit(request.url);query=parse_qs(parts.query)
    dataset=query.get('dataset',[]);identity=query.get('data_id',query.get('stock_id',[]))
    context=current_correlation();ticker=context.get('ticker','')
    if (request.method!='GET' or parts.scheme!='https' or parts.hostname!='api.finmindtrade.com'
        or parts.port not in (None,443) or parts.username or parts.password
        or parts.path not in ('/api/v3/data','/api/v4/data')
        or len(dataset)!=1 or dataset[0]not in _DATASETS
        or len(identity)!=1 or not ticker or identity[0]!=ticker.split('.')[0]):return
    adapter=session.get_adapter(request.url)
    if (type(adapter)is not requests.adapters.HTTPAdapter or adapter.max_retries.total!=0
        or not isinstance(response,requests.Response) or response.request is not request
        or getattr(response,'from_cache',False) or not response._content_consumed):return
    record_source_audit_entries([{**context,'source':_DATASETS[dataset[0]],
        'provider':'FinMind native HTTP','event_kind':'http_transport_receipt',
        'selection_policy':'transport-receipt-only:v1','status':'success'if response.status_code<400 else'error',
        'record_count':0,'http_request_sent':True,'http_status':response.status_code,
        'response_bytes':len(response.content),'response_sha256':sha256(response.content).hexdigest(),
        'duration_ms':max(0,int((time.monotonic()-started)*1000)),
        'message':'Native SDK transport receipt only; parsed data is separately audited.'}])


def observe_loader(loader):
    import requests
    session=getattr(loader,'_FinMindApi__session',None)
    if type(session)is not requests.Session:return loader
    with _LOCK:
        if getattr(session,'_stock_transport_receipts_installed',False):return loader
        original=session.send
        if getattr(original,'__func__',None)is not requests.Session.send:return loader
        def observed(request,*args,**kwargs):
            started=time.monotonic()
            response=original(request,*args,**kwargs)
            try:_record(session,request,response,started)
            except Exception:pass
            return response
        session.send=observed
        session._stock_transport_receipts_installed=True
    return loader


def observed_loader_class(base):
    class ObservedLoader(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            try:observe_loader(self)
            except Exception:pass
    ObservedLoader.__name__=base.__name__
    return ObservedLoader
