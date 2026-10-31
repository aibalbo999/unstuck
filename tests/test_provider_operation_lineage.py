import asyncio,copy
from data_fetch.provider_execution import fetch_provider_results
from data_fetch.provider_base import DataProvider
from data_fetch.types import FetchRequest,ProviderResult
from provider_correlation import correlation_scope,current_correlation,current_source_identity,source_operation
from provider_acquisition import observation_kind

REQ=FetchRequest.from_ticker('2330.TW',record_provider_sla=False)
class Manual(DataProvider):
    source='macro_indicators';name='FRED macro indicators'
    def __init__(self,cache=False):
        self.seen=[];self.value={'indicators':{'x':1}}
        self.audit={'source':self.source,'provider':self.name,'status':'success','record_count':1,'cache_hit':cache,'stale':False,'fetched_at_epoch':123}
    def fetch(self,request,context=None):
        self.seen.append((current_correlation(),current_source_identity()))
        return ProviderResult(self.source,self.name,'success',value=self.value,audit=self.audit)

def run(providers,context=None):
    with correlation_scope(replace=True,job_id='job',ticker='2330.TW',fetch_id='root-fetch'):
        before=current_correlation();result=asyncio.run(fetch_provider_results(REQ,providers,context or{}))
        assert current_correlation()==before and current_source_identity() is None
        return result

def test_manual_provider_result_binds_same_thread_local_source_operation():
    p=Manual();a=copy.deepcopy(p.audit);r,=run([p]);seen,owner=p.seen[0]
    assert owner==(p.source,p.name)
    assert r.audit['operation_id']==seen['operation_id']
    assert r.audit['fetch_id']==seen['fetch_id']=='root-fetch'
    assert r.value is p.value and r.status=='success'
    assert p.audit==a and r.audit is not p.audit
    assert 'http_request_sent'not in r.audit

def test_sibling_calls_cannot_borrow_operations():
    a,b=Manual(),Manual();x,y=run([a,b])
    assert x.audit['operation_id']!=y.audit['operation_id']
    assert x.audit['operation_id']==a.seen[0][0]['operation_id']
    assert y.audit['operation_id']==b.seen[0][0]['operation_id']

def test_cached_result_keeps_original_cache_date_and_no_native_send():
    p=Manual(cache=True);r,=run([p]);assert r.audit['cache_hit'] is True and r.audit['fetched_at_epoch']==123
    row={'source':r.source,'provider':r.provider,'status':r.status,'record_count':1,'message':'','details':r.audit}
    assert observation_kind(row)=='fresh_cache_count'
    assert r.audit.get('http_request_sent')is not True

def test_existing_inner_operation_is_never_relabelled():
    class Inner(Manual):
        async def fetch_async(self,*a,**k):
            with source_operation(self.source,self.name):
                self.inner=current_correlation();return ProviderResult(self.source,self.name,'success',value=self.value,audit={**self.audit,**self.inner})
    p=Inner();r,=run([p]);assert r.audit['operation_id']==p.inner['operation_id']

def test_core_cache_does_not_hide_new_provider_error():
    class Failed(Manual):
        def fetch(self,*a,**k):self.seen.append(current_correlation());raise ValueError('provider failed')
    p=Failed();r,=run([p],{'data':{'_cache_hit':True}})
    assert r.status=='error'and r.audit['error_kind']=='ValueError'
    assert r.audit['cache_hit']is False
    assert r.audit['operation_id']==p.seen[0]['operation_id']
    row={'source':r.source,'provider':r.provider,'status':r.status,'record_count':0,'message':r.audit['message'],'details':r.audit}
    assert observation_kind(row)=='failed_count'
    assert r.audit.get('http_request_sent')is not True


def test_default_error_propagation_preserves_exception_identity():
    from data_fetch.provider_execution import fetch_correlated_provider
    error=ValueError('native failure')
    class Failed(Manual):
        def fetch(self,*a,**k):raise error
    import pytest
    with pytest.raises(ValueError) as caught:
        asyncio.run(fetch_correlated_provider(Failed(),REQ,{}))
    assert caught.value is error
    assert current_source_identity() is None

def test_cancelled_provider_is_not_converted_to_failure_or_success():
    from data_fetch.provider_execution import fetch_correlated_provider
    import pytest
    class Cancelled(Manual):
        async def fetch_async(self,*a,**k):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(fetch_correlated_provider(Cancelled(),REQ,{},capture_errors=True))
    assert current_source_identity() is None

def test_existing_cache_provenance_is_not_replaced():
    p=Manual(cache=True)
    p.audit.update(operation_id='historical-operation',fetch_id='historical-fetch',ticker='2330.TW')
    r,=run([p])
    assert r.audit['operation_id']=='historical-operation'
    assert r.audit['fetch_id']=='historical-fetch'
    assert r.audit['fetched_at_epoch']==123
    assert 'http_request_sent'not in r.audit


def test_partial_existing_provenance_cannot_borrow_current_fetch():
    p=Manual(cache=True);p.audit['operation_id']='historical-operation'
    r,=run([p])
    assert r.audit['operation_id']=='historical-operation'
    assert 'fetch_id'not in r.audit and 'job_id'not in r.audit
