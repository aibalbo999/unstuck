"""Actual owned-session response to SDK input, without external requests."""
from copy import deepcopy
import json
import pandas as pd
import pytest
import requests
from provider_correlation import correlation_scope, source_operation, provider_attempt

DATASET='TaiwanStockInstitutionalInvestorsBuySell'
ROWS=[{'date':'2026-11-04','stock_id':'2330','name':'Foreign_Investor','buy':12000,'sell':5000}]

@pytest.fixture
def native(monkeypatch,tmp_path):
    import provider_sla
    from settings import storage
    from finmind_transport_receipts import observe_loader
    events=[];state={'rows':deepcopy(ROWS),'calls':0,'original_recorder':provider_sla.record_source_audit_entries}
    monkeypatch.setattr(storage,'CACHE_DIR',str(tmp_path/'originals'))
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:events.extend(deepcopy(entries)))
    def send(self,request,*args,**kwargs):
        state['calls']+=1
        r=requests.Response();r.request=request;r.url=request.url;r.status_code=state.get('status',200)
        r._content_consumed=state.get('consumed',True);r.from_cache=state.get('from_cache',False)
        r._content=state.get('body')or json.dumps({'msg':'success','status':200,'data':state['rows']}).encode()
        r.headers.update(state.get('headers',{}));r.history=state.get('history',[])
        return r
    monkeypatch.setattr(requests.Session,'send',send)
    class Loader:
        def __init__(self):self._FinMindApi__session=requests.Session()
        def taiwan_stock_institutional_investors(self,stock_id,start_date,end_date):
            r=self._FinMindApi__session.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':DATASET,'data_id':stock_id,'stock_id':'','start_date':start_date,'end_date':end_date,'token':'private-token'})
            return pd.DataFrame(r.json()['data'])
    loader=Loader();observe_loader(loader)
    return loader,state,events

def acquire(native):
    from finmind_dataset_originals import bind_sdk_frame
    loader,state,events=native
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='current-fetch'), source_operation('institutional_trading','FinMind'),provider_attempt('FinMind',1):
        r=loader._FinMindApi__session.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':DATASET,'data_id':'2330','stock_id':'','start_date':'2026-10-01','end_date':'2026-11-04','token':state.get('token','private-token')})
        frame=pd.DataFrame(r.json()['data'])
        if state.get('tamper'):frame.loc[0,'buy']+=1
        if state.get('cast_float'):frame['buy']=frame['buy'].astype(float)
        before=frame.copy(deep=True)
        proof=bind_sdk_frame(loader,frame,'2330.TW',DATASET)
        pd.testing.assert_frame_equal(frame,before)
        return proof

def test_complete_native_original_is_bound_to_exact_sdk_input(native):
    proof=acquire(native);loader,state,events=native
    assert proof and proof['schema']=='finmind-native-body-to-sdk-input:v1'
    assert proof['sdk_row_count']==1 and proof['derived_metrics_verified']is False
    assert proof['independent_primary_source_verified']is False
    receipt=events[0]['raw_http_receipt']
    from official_response_evidence import read_response
    assert json.loads(read_response(receipt))['data']==ROWS
    assert receipt['evidence_kind']=='decoded_complete_http_response_body'
    assert receipt['response_complete']is True and state['calls']==1
    assert 'private-token'not in str(events)and 'token'not in receipt['source_url']

def test_research_scope_suppresses_new_originals_and_sla(native,monkeypatch):
    from finmind_transport_receipts import receipt_observation_scope
    import official_response_evidence
    monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**k:pytest.fail('Research must not archive native bodies'))
    with receipt_observation_scope(False):assert acquire(native)is None
    assert native[1]['calls']==1 and native[2]==[]

@pytest.mark.parametrize('mode',['frame_tamper','foreign_issuer','future','outside_period','secret_echo','escaped_secret','extra_column','bool_number','nonfinite','cached','history','partial','range','length','empty','duplicate_key','archive_failure'])
def test_ambiguous_input_never_upgrades_original_or_changes_response(native,monkeypatch,mode):
    _,s,events=native
    if mode=='frame_tamper':s['tamper']=True
    elif mode=='foreign_issuer':s['rows'][0]['stock_id']='9999'
    elif mode=='future':s['rows'][0]['date']='2099-11-04'
    elif mode=='outside_period':s['rows'][0]['date']='2026-09-01'
    elif mode=='secret_echo':s['rows'][0]['name']='private-token'
    elif mode=='escaped_secret':s['token']=s['rows'][0]['name']='私密金鑰'
    elif mode=='extra_column':s['rows'][0]['unknown']='untrusted'
    elif mode=='bool_number':s['rows'][0]['buy']=True
    elif mode=='nonfinite':s['rows'][0]['buy']=float('nan')
    elif mode=='cached':s['from_cache']=True
    elif mode=='history':s['history']=[requests.Response()]
    elif mode=='partial':s['status']=206
    elif mode=='range':s['headers']={'Content-Range':'bytes 0-100/999'}
    elif mode=='length':s['headers']={'Content-Length':'1'}
    elif mode=='empty':s['rows']=[]
    elif mode=='duplicate_key':s['body']=json.dumps({'msg':'success','data':ROWS}).replace('"data":','"status":500,"status":200,"data":').encode()
    else:
        import official_response_evidence
        monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**k:(_ for _ in()).throw(OSError('unit failure')))
    if mode=='nonfinite':
        with pytest.raises(ValueError):acquire(native)  # Keep the SDK decoder's original refusal.
    else:assert acquire(native)is None
    assert s['calls']==1
    assert all(row['record_count']==0 for row in events)
    if mode!='frame_tamper':assert all('raw_http_receipt'not in row for row in events)

def test_numeric_cast_is_same_input_and_transport_still_zero_acquisition(native):
    native[1]['cast_float']=True
    proof=acquire(native);assert proof and proof['sdk_row_count']==1
    from provider_observation_details import observation_details
    from provider_acquisition import observation_kind
    for row in native[2]:
        assert observation_kind({**row,'details':observation_details(row)})=='aggregate_count'
        assert row['record_count']==0

@pytest.mark.parametrize('code',[429,503,504])
def test_real_error_response_remains_transport_error_without_data(native,code):
    native[1]['status']=code
    assert acquire(native)is None
    assert native[1]['calls']==1 and len(native[2])==1
    assert native[2][0]['status']=='error'and native[2][0]['http_status']==code
    assert native[2][0]['record_count']==0 and 'raw_http_receipt'not in native[2][0]

def test_zero_exponent_normalization_is_bounded():
    from decimal import Decimal
    from datetime import date
    from finmind_dataset_originals import _rows
    rows=deepcopy(ROWS);rows[0]['buy']=Decimal('0E+999999999')
    normalized=_rows(rows,'2330.TW',DATASET,date(2026,10,1),date(2026,11,4))
    assert normalized[0]['buy']==['number','0']

def _audit(proof):
    return {'source':'institutional_trading','provider':'FinMind','status':'degraded_enrichment','cache_hit':False,'record_count':1,
        **{k:proof[k]for k in('ticker','fetch_id','operation_id')},'provider_attempts':[{'attempt_id':proof['transport_attempt_id'],'status':'success','source':'institutional_trading','provider':'FinMind'}],'sdk_input_lineages':[proof]}

def test_public_input_fingerprint_does_not_leak_or_claim_metrics(native):
    from provider_observation_details import observation_details
    proof=acquire(native);entry=_audit(proof);before=deepcopy(entry)
    entry['sdk_input_lineages'][0]['private_path']='/private/not-public'
    public=observation_details(entry)['sdk_input_lineages'][0]
    assert 'private_path'not in public and public['derived_metrics_verified']is False
    assert entry['sdk_input_lineages'][0]['private_path']=='/private/not-public'
    assert {k:v for k,v in entry['sdk_input_lineages'][0].items()if k!='private_path'}==before['sdk_input_lineages'][0]

@pytest.mark.parametrize('damage',['provider','source','cache','empty_status','no_data_records','fetch','operation','issuer','attempt','attempt_error','foreign_attempt','row_count_bool','body_count','hash','future','old','date_order','invalid_date','date_future','metrics_upgrade','primary_upgrade','credentials','http_bool','duplicate_dataset'])
def test_unbound_or_escalated_input_metadata_is_not_persisted(native,damage):
    import time
    from provider_observation_details import observation_details
    entry=_audit(acquire(native));p=entry['sdk_input_lineages'][0]
    if damage=='provider':entry['provider']='Other'
    elif damage=='source':entry['source']='financial_statements'
    elif damage=='cache':entry['cache_hit']=True
    elif damage=='empty_status':entry['status']='unavailable'
    elif damage=='no_data_records':entry['record_count']=0
    elif damage=='fetch':entry['fetch_id']='other'
    elif damage=='operation':entry['operation_id']='other'
    elif damage=='issuer':p['ticker']='9999.TW'
    elif damage=='attempt':entry['provider_attempts']=[]
    elif damage=='attempt_error':entry['provider_attempts'][0]['status']='error'
    elif damage=='foreign_attempt':entry['provider_attempts'][0]['provider']='Other'
    elif damage=='row_count_bool':p['sdk_row_count']=True
    elif damage=='body_count':p['native_response_bytes']=0
    elif damage=='hash':p['sdk_rows_sha256']='bad'
    elif damage=='future':p['native_received_at_epoch']=time.time()+100
    elif damage=='old':p['native_received_at_epoch']=time.time()-181
    elif damage=='date_order':p['query_end_date']='2026-09-30'
    elif damage=='invalid_date':p['query_end_date']='2026-02-31'
    elif damage=='date_future':p['query_end_date']='2099-12-31'
    elif damage=='metrics_upgrade':p['derived_metrics_verified']=True
    elif damage=='primary_upgrade':p['independent_primary_source_verified']=True
    elif damage=='credentials':p['request_url_credentials_redacted']=False
    elif damage=='http_bool':p['native_http_status']=True
    else:entry['sdk_input_lineages']*=2
    assert 'sdk_input_lineages'not in observation_details(entry)

def test_outer_research_scope_cannot_be_reenabled_by_nested_normal_scope(native):
    from finmind_transport_receipts import receipt_observation_scope
    with receipt_observation_scope(False),receipt_observation_scope(True):assert acquire(native)is None
    assert native[2]==[]
    assert acquire(native)is not None  # Both context tokens were restored.

@pytest.mark.parametrize('research',[False,True])
def test_actual_typed_institutional_cold_and_warm_keep_input_identity(native,monkeypatch,research):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import taiwan
    import official_institutional_source as official
    from data_fetch.institutional_provider import fetch_institutional_result
    from data_fetch.types import FetchRequest
    from provider_observation_details import observation_details
    loader,state,events=native
    monkeypatch.setattr(taiwan,'DataLoader',lambda:loader)
    monkeypatch.setattr(official,'expected_sessions',lambda *a,**k:['2026-11-04'])
    monkeypatch.setattr(official,'recover_institutional_observations',lambda ticker,value,**kw:(value,{}))
    cache_store.set_cache_backend(InMemoryCache())
    try:
        request=FetchRequest.from_ticker('2330.TW',record_provider_sla=not research)
        with correlation_scope(replace=True,ticker=request.ticker,fetch_id='cold'):
            cold=fetch_institutional_result(request)
        assert cold.value['daily_category_observations'][0]['net_buy_shares']==7000
        assert cold.value['source_provenance']['evidence_kind']=='sdk_dataframe_json_not_raw_http'
        if research:
            assert events==[] and 'native_sdk_input'not in cold.value['source_provenance']
            assert 'sdk_input_lineages'not in observation_details(cold.audit)
        else:
            proof=observation_details(cold.audit)['sdk_input_lineages'][0]
            assert proof['sdk_row_count']==1 and proof['derived_metrics_verified']is False
        original=deepcopy(cold.value['source_provenance'])
        with correlation_scope(replace=True,ticker=request.ticker,fetch_id='warm'):
            warm=fetch_institutional_result(request)
        assert warm.audit['cache_hit']is True and state['calls']==1
        assert 'sdk_input_lineages'not in observation_details(warm.audit)
        assert warm.value['source_provenance']==original
    finally:cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('research',[False,True])
def test_actual_twse_sdk_input_proof_does_not_promote_single_quarter_to_ttm(native,monkeypatch,research):
    from urllib.parse import parse_qs,urlsplit
    from finmind_transport_receipts import observed_loader_class
    import external_data_twse as twse
    from data_fetch.taiwan_providers import TwseOfficialProvider
    from data_fetch.types import FetchRequest
    from provider_observation_details import observation_details
    _,state,events=native
    rows={
        'TaiwanStockFinancialStatements':[{'date':'2026-09-30','stock_id':'2330','type':'Revenue','value':100}],
        'TaiwanStockBalanceSheet':[{'date':'2026-09-30','stock_id':'2330','type':'TotalLiabilities','value':20}],
        'TaiwanStockCashFlowsStatement':[{'date':'2026-09-30','stock_id':'2330','type':'NetCashInflowFromOperatingActivities','value':30}],
    }
    def send(self,request,*a,**k):
        dataset=parse_qs(urlsplit(request.url).query)['dataset'][0]
        state['calls']+=1;r=requests.Response();r.request=request;r.url=request.url;r.status_code=200
        r._content_consumed=True;r._content=json.dumps({'msg':'success','status':200,'data':rows[dataset]}).encode();return r
    monkeypatch.setattr(requests.Session,'send',send)
    class Loader:
        def __init__(self):self._FinMindApi__session=requests.Session()
        def query(self,dataset,stock_id,start_date):
            r=self._FinMindApi__session.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':dataset,'data_id':stock_id,'stock_id':'','start_date':start_date,'token':'private-token'})
            return pd.DataFrame(r.json()['data'])
        def taiwan_stock_income_statement(self,stock_id,start_date):return self.query('TaiwanStockFinancialStatements',stock_id,start_date)
        def taiwan_stock_balance_sheet(self,stock_id,start_date):return self.query('TaiwanStockBalanceSheet',stock_id,start_date)
        def taiwan_stock_cash_flows_statement(self,stock_id,start_date):return self.query('TaiwanStockCashFlowsStatement',stock_id,start_date)
    monkeypatch.setattr(twse,'DataLoader',observed_loader_class(Loader));monkeypatch.setattr(twse,'FINMIND_API_TOKEN','')
    request=FetchRequest.from_ticker('2330.TW',record_provider_sla=not research)
    with correlation_scope(replace=True,ticker=request.ticker,fetch_id='financial-inputs'):
        result=TwseOfficialProvider().fetch(request)
    assert result.value['revenue_ttm_raw']is None and result.value['total_debt_raw']==20
    assert 'native_sdk_inputs'not in result.value
    assert result.audit['record_count']==len(result.value), 'Evidence handoff must not inflate data record counts'
    assert state['calls']==3
    if research:
        assert events==[] and 'native_sdk_inputs'not in result.value
        assert 'sdk_input_lineages'not in observation_details(result.audit)
    else:
        inputs=observation_details(result.audit)['sdk_input_lineages']
        assert len(inputs)==3 and {p['dataset']for p in inputs}==set(rows)
        assert all(p['derived_metrics_verified']is False for p in inputs)
        assert len(events)==3 and all(e['record_count']==0 for e in events)

def test_common_request_boundary_suppresses_native_research_observation(native):
    import asyncio
    from data_fetch.provider_execution import fetch_correlated_provider
    from data_fetch.provider_base import DataProvider
    from data_fetch.types import FetchRequest,ProviderResult
    class Provider(DataProvider):
        source='institutional_trading';name='FinMind'
        def fetch(self,request,context=None):
            assert acquire(native)is None
            return ProviderResult(self.source,self.name,'unavailable',{})
    request=FetchRequest.from_ticker('2330.TW',record_provider_sla=False)
    asyncio.run(fetch_correlated_provider(Provider(),request,{}))
    assert native[1]['calls']==1 and native[2]==[]

def test_sql_keeps_secret_free_input_proof_without_extra_data_acquisition(native):
    import sqlite3,time
    import provider_sla
    from provider_acquisition import project_acquisition_events
    proof=acquire(native);entry=_audit(proof);entry.update(event_kind='aggregate',message='unit input only')
    # The recorder captures its isolated database at module import; changing
    # CACHE_DIR for body archival must not redirect this SQL assertion.
    path=provider_sla.TASK_DB_PATH
    with sqlite3.connect(path)as db:
        db.row_factory=sqlite3.Row
        from provider_sla_schema import init_provider_sla_schema
        init_provider_sla_schema(db)
        before=db.execute('SELECT coalesce(max(id),0) FROM provider_sla_events').fetchone()[0]
    native[1]['original_recorder']([*native[2],entry])
    with sqlite3.connect(path)as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('SELECT * FROM provider_sla_events WHERE id>? ORDER BY id',(before,))]
    assert len(rows)==2 and 'private-token'not in str(rows)
    details=json.loads(rows[-1]['details_json'])
    assert details['sdk_input_lineages'][0]==proof
    assert all('raw_response_path'not in r for r in details['sdk_input_lineages'])
    summary=project_acquisition_events(rows,window='last_24h',now=time.time())
    group=next(g for g in summary['sources']if g['source']=='institutional_trading')
    assert group['fetch_attempts']==1 and group['degraded_count']==1 and group['fetched_count']==0
