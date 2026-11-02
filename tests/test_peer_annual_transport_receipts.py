"""Annual peer reads retain the root operation and never invent SDK sends."""
from types import SimpleNamespace
import pytest
from provider_correlation import correlation_scope,source_operation,current_correlation
import provider_sla
import yfinance_transport_receipts as transport

ROOT='9904.TW';PEER='9802.TW'
BASE='https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/'+PEER

def receive(*,symbol=PEER,kind='annualTotalRevenue',cached=False,status=200):
    url=BASE.replace(PEER,symbol)+'?symbol='+symbol+'&type='+kind
    r=SimpleNamespace(url=url,status_code=status,content=b'private-body',from_cache=cached)
    transport._record('GET',url,None,r,0,False)
    return r

def setup(monkeypatch):
    rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    monkeypatch.setattr(transport,'observe_yfinance',lambda:True)
    return rows

def test_annual_peer_receipt_is_transport_only_bound_to_root(monkeypatch):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            owner=current_correlation()
            with transport.observe_peer_annual_statements(PEER):r=receive()
    assert r.content==b'private-body' and len(rows)==1
    e=rows[0]
    assert e['ticker']==ROOT and e['peer_symbol']==PEER and e['operation_id']==owner['operation_id']
    assert e['source']=='dynamic_peer_metrics' and e['record_count']==0
    assert e['event_kind']=='http_transport_receipt' and e['http_request_sent']is True
    assert 'private-body'not in str(rows)

@pytest.mark.parametrize('options',[{'cached':True},{'symbol':ROOT},{'symbol':'2330.TW'},{'kind':'quarterlyTotalRevenue'},{'kind':'annualFake'}])
def test_wrong_symbol_period_unknown_field_or_cache_not_borrowed(monkeypatch,options):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_annual_statements(PEER):receive(**options)
    assert not rows

def test_scope_cleanup_and_source_binding(monkeypatch):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('market_data','yfinance'):
            with transport.observe_peer_annual_statements(PEER):receive()
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with pytest.raises(RuntimeError):
                with transport.observe_peer_annual_statements(PEER):raise RuntimeError('same')
            receive()
    assert not rows

def test_native_429_remains_failure(monkeypatch):
    rows=setup(monkeypatch)
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            with transport.observe_peer_annual_statements(PEER):receive(status=429)
    assert len(rows)==1 and rows[0]['status']=='error' and rows[0]['record_count']==0


def test_native_original_preserves_peer_body_without_rebinding_root():
    import json
    from test_yahoo_annual_originals import response
    from yahoo_annual_original import capture_peer_annual_response,capture_annual_response
    from official_response_evidence import read_response
    r=response();r.url=r.url.replace('1623.TW',PEER);r.request.url=r.url
    r.content=r.content.replace(b'1623.TW',PEER.encode())
    with correlation_scope(replace=True,ticker=ROOT,fetch_id='f'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            owner=current_correlation()
            proof=capture_peer_annual_response(r,binding=owner,symbol=PEER)
            assert capture_annual_response(r,binding=owner)is None
    assert proof and read_response(proof)==r.content
    assert PEER in proof['source_url'] and 'crumb'not in proof['source_url']
    assert 'private-test-value'not in json.dumps(proof)
    assert proof['financial_semantics_verified']is False


@pytest.mark.parametrize('cached',[False,True])
def test_real_peer_workflow_keeps_two_annual_reads_values_and_owner(monkeypatch,cached):
    import pandas as pd
    from datetime import date
    from data_fetch.market_sources import peers
    from test_peer_acquisition_recovery import master
    rows=setup(monkeypatch);calls=[]
    monkeypatch.setattr(peers,'_today',lambda:date(2026,9,25))
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[master('1476',category='紡織纖維'),master('1477',category='紡織纖維')])
    class Stock:
        info={'symbol':'1477.TW','quoteType':'EQUITY','industry':'Apparel Manufacturing',
              'grossMargins':.4,'operatingMargins':.2,'profitMargins':.1,'returnOnEquity':.12,
              'trailingPE':15,'priceToBook':2,'priceToSalesTrailing12Months':3,'totalRevenue':9e9}
        @property
        def financials(self):
            calls.append('financials')
            if not cached:receive(symbol='1477.TW')
            return pd.DataFrame([[4e9]],index=['Total Revenue'],columns=pd.to_datetime(['2025-12-31']))
        @property
        def balance_sheet(self):
            calls.append('balance_sheet')
            if not cached:receive(symbol='1477.TW',kind='annualTotalAssets')
            return pd.DataFrame([[2e9]],index=['Total Assets'],columns=pd.to_datetime(['2025-12-31']))
    monkeypatch.setattr(peers.yf,'Ticker',lambda symbol:Stock())
    with correlation_scope(replace=True,ticker='1476.TW',fetch_id='root-fetch'):
        with source_operation('dynamic_peer_metrics','FinMind/yfinance'):
            owner=current_correlation();result=peers.fetch_dynamic_peer_metrics_with_diagnostics('1476.TW','fixture','Consumer Cyclical','Apparel Manufacturing',{})
    assert calls==['financials','balance_sheet']
    assert result['peers'][0]['asset_turnover']==2.0 and result['peers'][0]['metrics_status']=='complete'
    assert len(rows)==(0 if cached else 2)
    assert all(e['ticker']=='1476.TW' and e['peer_symbol']=='1477.TW' and e['fetch_id']=='root-fetch' and e['operation_id']==owner['operation_id'] for e in rows)
    assert result['peers'][0]['metric_sources']['asset_turnover']['observation_note']=='same-date SDK annual frames; HTTP cache status unknown'
