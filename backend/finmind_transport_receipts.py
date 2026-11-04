"""Observe one SDK-owned Session; never modify SDK/global requests or data."""
from hashlib import sha256
from urllib.parse import urlsplit,parse_qs
import time
import threading
import weakref
from contextlib import contextmanager
from contextvars import ContextVar

_RECORD_RECEIPTS=ContextVar('finmind_receipt_observation',default=True)

@contextmanager
def receipt_observation_scope(enabled):
    token=_RECORD_RECEIPTS.set(_RECORD_RECEIPTS.get()and enabled is True)
    try:yield
    finally:_RECORD_RECEIPTS.reset(token)

_LOCK=threading.Lock()
_DATASETS={'TaiwanStockMonthRevenue':'monthly_revenue',
 'TaiwanStockInstitutionalInvestorsBuySell':'institutional_trading',
 'TaiwanStockNews':'recent_catalysts','TaiwanStockPER':'pe_river_chart',
 'TaiwanStockFinancialStatements':'financial_statements',
 'TaiwanStockBalanceSheet':'financial_statements',
 'TaiwanStockCashFlowsStatement':'financial_statements'}


def _record(session,request,response,started):
    if not _RECORD_RECEIPTS.get():return None
    import requests
    from provider_correlation import current_correlation,current_source_identity
    from provider_sla import record_source_audit_entries
    parts=urlsplit(request.url);query=parse_qs(parts.query)
    dataset=query.get('dataset',[]);identity=query.get('data_id',query.get('stock_id',[]))
    context=current_correlation();ticker=context.get('ticker','')
    owner=current_source_identity()
    if (request.method=='GET'and parts.scheme=='https'and parts.hostname=='api.web.finmindtrade.com'
            and parts.port in(None,443)and not parts.username and not parts.password and not parts.query and not parts.fragment
            and parts.path=='/v2/user_info'and owner and owner[0]in set(_DATASETS.values())|{'twse_official','dynamic_peer_metrics','peer_discovery'}
            and owner[1].startswith('FinMind')and all(context.get(k)for k in('ticker','fetch_id','operation_id'))):
        adapter=session.get_adapter(request.url)
        if(type(adapter)is requests.adapters.HTTPAdapter and adapter.max_retries.total==0
                and type(response)is requests.Response and response.request is request and response.url==request.url
                and not response.history and not getattr(response,'from_cache',False)
                and type(response.status_code)is int and response._content_consumed is True):
            # Account contents/headers/hash are private and are not evidence
            # for company data. Keep only this actual zero-record HTTP receipt.
            record_source_audit_entries([{**context,'source':owner[0],'provider':'FinMind account native HTTP',
                'event_kind':'http_transport_receipt','selection_policy':'transport-receipt-only:v1',
                'record_count':0,'status':'success'if response.status_code==200 else'error',
                'http_request_sent':True,'http_status':response.status_code,'http_status_observed':True,
                'response_complete':True,'cache_hit':False,'duration_ms':max(0,int((time.monotonic()-started)*1000)),
                'message':'Native SDK login HTTP only; account body, headers and credentials are not retained.'}])
        return None
    if (request.method!='GET' or parts.scheme!='https' or parts.hostname!='api.finmindtrade.com'
        or parts.port not in (None,443) or parts.username or parts.password
        or parts.path not in ('/api/v3/data','/api/v4/data')
        or len(dataset)!=1 or dataset[0]not in _DATASETS
        or len(identity)!=1 or not ticker or identity[0]!=ticker.split('.')[0]):return
    adapter=session.get_adapter(request.url)
    if (type(adapter)is not requests.adapters.HTTPAdapter or adapter.max_retries.total!=0
        or not isinstance(response,requests.Response) or response.request is not request
        or getattr(response,'from_cache',False) or not response._content_consumed):return
    source=_DATASETS[dataset[0]]
    if source=='financial_statements' and current_source_identity()==('twse_official','FinMind TWSE official'):
        source='twse_official'
    entry={**context,'source':source,
        'provider':'FinMind native HTTP','event_kind':'http_transport_receipt',
        'selection_policy':'transport-receipt-only:v1','status':'success'if response.status_code<400 else'error',
        'record_count':0,'http_request_sent':True,'http_status':response.status_code,
        'component_statuses':{dataset[0]:{'dataset':dataset[0],
            'status':'transport_received','http_status':response.status_code}},
        'response_bytes':len(response.content),'response_sha256':sha256(response.content).hexdigest(),
        'duration_ms':max(0,int((time.monotonic()-started)*1000)),
        'message':'Native FinMind SDK transport only, not direct exchange proof; parsed data is separately audited.'}
    capsule=None;dataset_original=False
    if dataset[0]=='TaiwanStockMonthRevenue':
        try:
            from finmind_monthly_lineage import capture_monthly_response
            capsule=capture_monthly_response(request,response,context)
        except Exception:pass
    elif dataset[0]=='TaiwanStockPER':
        try:
            from finmind_per_lineage import capture_per_response
            capsule=capture_per_response(request,response,context)
        except Exception:pass
    elif dataset[0]in {'TaiwanStockInstitutionalInvestorsBuySell','TaiwanStockFinancialStatements','TaiwanStockBalanceSheet','TaiwanStockCashFlowsStatement'}:
        try:
            from finmind_dataset_originals import capture_dataset_response
            capsule=capture_dataset_response(request,response,context)
            dataset_original=capsule is not None
        except Exception:pass
    if capsule is not None:entry['raw_http_receipt']=capsule.receipt
    if dataset_original:
        entry.update(http_status_observed=True,response_complete=True,cache_hit=False)
    record_source_audit_entries([entry])
    return capsule


def observe_loader(loader):
    import requests
    session=getattr(loader,'_FinMindApi__session',None)
    if type(session)is not requests.Session:return loader
    with _LOCK:
        if getattr(session,'_stock_transport_receipts_installed',False):return loader
        original=session.send
        if getattr(original,'__func__',None)is not requests.Session.send:return loader
        try:owner_ref=weakref.ref(loader)
        except TypeError:owner_ref=lambda:None
        def observed(request,*args,**kwargs):
            started=time.monotonic()
            response=original(request,*args,**kwargs)
            try:
                capsule=_record(session,request,response,started)
                owner=owner_ref()
                if capsule is not None and owner is not None:
                    dataset=getattr(capsule,'dataset','')
                    key=('_stock_per_transport_capsules'if dataset=='TaiwanStockPER'else
                         '_stock_dataset_transport_capsules'if dataset in {'TaiwanStockInstitutionalInvestorsBuySell','TaiwanStockFinancialStatements','TaiwanStockBalanceSheet','TaiwanStockCashFlowsStatement'}else '_stock_monthly_transport_capsules')
                    setattr(owner,key,[*getattr(owner,key,[])[-7:],capsule])
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
            # Active request policy is separate from optional passive telemetry.
            # A changed real SDK contract must fail closed, not run unbounded.
            from finmind_loader_limits import install_loader_limits
            install_loader_limits(self)
    if callable(getattr(base,'login_by_token',None)):
        def login(self,*args,**kwargs):
            # DataLoader calls login during its constructor. Install before its
            # first user_info GET, without replacing or skipping the SDK login.
            try:observe_loader(self)
            except Exception:pass
            from finmind_loader_limits import install_loader_limits,call_native_login
            install_loader_limits(self)
            return call_native_login(super(ObservedLoader,self).login_by_token,*args,**kwargs)
        ObservedLoader.login_by_token=login
    import inspect
    ObservedLoader._stock_native_token_constructor=(base.__module__.startswith('FinMind.')
        and 'token'in inspect.signature(base.__init__).parameters)
    ObservedLoader.__name__=base.__name__
    return ObservedLoader
