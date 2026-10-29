"""Peer transport must belong to the exact root fetch and selected peer."""
from types import SimpleNamespace
import pytest
import provider_sla
from provider_correlation import correlation_scope, source_operation, current_correlation
import yfinance_transport_receipts as transport

ROOT='2356.TW';PEER='2382.TW'

def setup(monkeypatch):
    rows=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda value:rows.extend(value))
    monkeypatch.setattr(transport,'observe_yfinance',lambda:True)
    return rows

def receive(symbol=PEER, *, path=None, status=200, cached=False, stream=False):
    url='https://query2.finance.yahoo.com'+(path or '/v10/finance/quoteSummary/'+symbol)
    response=SimpleNamespace(url=url,status_code=status,content=b'private-body',from_cache=cached)
    transport._record('GET',url,None,response,0,stream)
    return response

@pytest.mark.parametrize('path',[None,'/v7/finance/quote?symbols=2382.TW'])
def test_selected_peer_is_owned_by_root_fetch_without_parsed_success(monkeypatch,path):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='fetch-root'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            owner=current_correlation()
            with transport.observe_peer_metrics(PEER):response=receive(path=path)
    assert response.content==b'private-body' and len(rows)==1
    row=rows[0]
    assert row['source']=='dynamic_peer_metrics' and row['ticker']==ROOT
    assert row['operation_id']==owner['operation_id'] and row['fetch_id']=='fetch-root'
    assert row['record_count']==0 and row['event_kind']=='http_transport_receipt'
    assert row['peer_symbol']==PEER and row['http_request_sent'] is True
    assert 'private-body' not in str(rows)

@pytest.mark.parametrize('options',[{'symbol':'2330.TW'},{'symbol':ROOT},{'path':'/v8/finance/chart/2382.TW'},
    {'path':'/v7/finance/quote?symbols=2382.TW,2330.TW'},{'cached':True},{'stream':True},
    {'path':'/v1/test/getcrumb'}])
def test_other_symbol_endpoint_sdk_cache_or_stream_never_borrowed(monkeypatch,options):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_metrics(PEER):receive(**options)
    assert not rows

@pytest.mark.parametrize('owner',[('market_data','yfinance'),('dynamic_peer_metrics','wrong-provider')])
def test_wrong_source_operation_refuses_receipt(monkeypatch,owner):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation(*owner):
            with transport.observe_peer_metrics(PEER):receive()
    assert not rows

def test_owner_change_and_exception_cleanup_cannot_reuse_scope(monkeypatch):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_metrics(PEER):
                with correlation_scope(operation_id='other-operation'):receive()
            with pytest.raises(RuntimeError):
                with transport.observe_peer_metrics(PEER):raise RuntimeError('original')
            receive()
    assert not rows

def test_native_429_is_failure_not_source_data_success(monkeypatch):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_metrics(PEER):receive(status=429)
    assert len(rows)==1 and rows[0]['status']=='error' and rows[0]['record_count']==0


def test_real_peer_workflow_preserves_root_owner_across_worker_threads(monkeypatch):
    from data_fetch.market_sources import peers
    from datetime import date
    rows=setup(monkeypatch);today=date(2026,10,30);symbols=['2382','3231']
    monkeypatch.setattr(peers,'_today',lambda:today)
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[{
        'stock_id':s,'stock_name':'Fixture '+s,'type':'twse','industry_category':'電腦及週邊設備業',
        'date':today.isoformat()} for s in ['2356',*symbols]])
    monkeypatch.setattr(peers,'fetch_peer_valuation_fallback',lambda *a,**k:{'metrics':{},'status':'valid_empty'})
    class Stock:
        def __init__(self,symbol):self.symbol=symbol
        @property
        def info(self):
            receive(self.symbol)
            return {'symbol':self.symbol,'quoteType':'EQUITY','trailingPE':10,'priceToBook':2}
    monkeypatch.setattr(peers.yf,'Ticker',Stock)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='threaded-fetch'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            owner=current_correlation()
            result=peers.fetch_dynamic_peer_metrics_with_diagnostics(ROOT,'Fixture','Technology','Computer Hardware',
                {'same_industry_peers':[{'stock_id':s}for s in symbols]})
    assert result['audit']['usable_count']>0 and len(rows)==2
    assert {r['peer_symbol']for r in rows}=={s+'.TW'for s in symbols}
    assert all(r['ticker']==ROOT and r['fetch_id']=='threaded-fetch' and r['operation_id']==owner['operation_id']for r in rows)


def test_peer_symbol_remains_in_persistable_bounded_details(monkeypatch):
    from provider_observation_details import observation_details
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_metrics(PEER):receive()
    details=observation_details(rows[0]);assert PEER in details['component_statuses']
    assert details['component_statuses'][PEER]['response_sha256']==rows[0]['response_sha256']

@pytest.mark.parametrize('path',[
    '/v10/finance/quoteSummary/2382.TW?symbol=2330.TW',
    '/v10/finance/quoteSummary/2382.TW?symbols=2330.TW',
])
def test_quote_identity_query_cannot_contradict_bound_peer(monkeypatch,path):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_metrics(PEER):receive(path=path)
    assert not rows
