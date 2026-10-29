from types import SimpleNamespace
import pytest
from provider_correlation import correlation_scope
import provider_sla
import yfinance_transport_receipts as transport

BASE='https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/2330.TW'
META={'ticker':'2330.TW','fetch_id':'fetch-1','operation_id':'annual-1'}

def setup(monkeypatch):
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows));monkeypatch.setattr(transport,'observe_yfinance',lambda:True);return events

def send(url=BASE+'?symbol=2330.TW&type=annualTotalRevenue',**kw):
 response=SimpleNamespace(url=url,status_code=kw.get('status',200),content=b'financial-secret',from_cache=kw.get('cached',False))
 transport._record(kw.get('method','GET'),url,None,response,0,kw.get('stream',False));return response


def test_actual_annual_timeseries_is_only_transport_not_parsed_success(monkeypatch):
 events=setup(monkeypatch)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch-1'):
  with transport.observe_annual_statements('2330.TW',META):send()
 assert len(events)==1 and events[0]['source']=='financial_statements'
 assert events[0]['operation_id']=='annual-1' and events[0]['fetch_id']=='fetch-1'
 assert events[0]['event_kind']=='http_transport_receipt' and events[0]['record_count']==0
 assert events[0]['http_request_sent'] is True and 'secret' not in str(events)


@pytest.mark.parametrize('url',[
 BASE+'?symbol=2330.TW&type=quarterlyTotalRevenue',
 BASE+'?symbol=2330.TW&type=annualTotalRevenue,quarterlyNetIncome',
 BASE+'?symbol=9999.TW&type=annualTotalRevenue',
 BASE.replace('2330.TW','9999.TW')+'?symbol=9999.TW&type=annualTotalRevenue',
 BASE+'?symbol=2330.TW&type=annualMadeUpField',
 'https://query2.finance.yahoo.com/v8/finance/chart/2330.TW',
])
def test_other_period_owner_endpoint_or_unknown_type_not_borrowed(monkeypatch,url):
 events=setup(monkeypatch)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch-1'):
  with transport.observe_annual_statements('2330.TW',META):send(url)
 assert not events


@pytest.mark.parametrize('kw',[{'cached':True},{'stream':True},{'method':'POST'}])
def test_cached_streaming_or_nonget_not_new_sample(monkeypatch,kw):
 events=setup(monkeypatch)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch-1'):
  with transport.observe_annual_statements('2330.TW',META):send(**kw)
 assert not events


def test_scope_cleanup_and_wrong_fetch_fail_closed(monkeypatch):
 events=setup(monkeypatch)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='other'):
  with transport.observe_annual_statements('2330.TW',META):send()
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch-1'):
  with pytest.raises(RuntimeError):
   with transport.observe_annual_statements('2330.TW',META):raise RuntimeError('original')
  send()
 assert not events


def test_429_remains_error_with_no_parsed_records(monkeypatch):
 events=setup(monkeypatch)
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch-1'):
  with transport.observe_annual_statements('2330.TW',META):send(status=429)
 assert len(events)==1 and events[0]['status']=='error' and events[0]['http_status']==429
 assert events[0]['record_count']==0


@pytest.mark.parametrize('sdk_cached',[False,True])
def test_three_existing_reads_keep_values_counts_and_operation_binding(monkeypatch,sdk_cached):
 from test_financial_statement_observation import StatementStock
 from data_fetch.yfinance_extractors import extract_financial_histories
 events=setup(monkeypatch)
 class Stock(StatementStock):
  def __getattr__(self,name):
   value=super().__getattr__(name)
   if not sdk_cached:
    field={'financials':'TotalRevenue','cashflow':'OperatingCashFlow','balance_sheet':'TotalAssets'}[name]
    send(BASE.replace('2330.TW','AAPL')+'?symbol=AAPL&type=annual'+field)
   return value
 stock=Stock()
 with correlation_scope(replace=True,ticker='AAPL',fetch_id='fetch-aapl'):
  result=extract_financial_histories(stock,'AAPL',[],data_loader_cls=None)
 assert dict(stock.calls)=={'financials':1,'cashflow':1,'balance_sheet':1}
 assert result['revenue_history']==[1.0,2.0] and result['fcf_history']==[0.2,0.4]
 audit=result['primary_financial_audit']
 receipts=[e for e in events if e.get('event_kind')=='http_transport_receipt']
 assert len(receipts)==(0 if sdk_cached else 3)
 assert all(e['operation_id']==audit['operation_id'] and e['fetch_id']=='fetch-aapl' for e in receipts)
 assert audit['retrieval_status']=='sdk_read_cache_unknown'
