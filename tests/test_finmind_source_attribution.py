"""Attribute native SDK financial GETs only to their actual bounded operation."""
import pytest,requests
from types import SimpleNamespace
import provider_sla
from provider_correlation import correlation_scope,source_operation
from finmind_transport_receipts import observe_loader


@pytest.mark.parametrize('dataset',['TaiwanStockFinancialStatements','TaiwanStockBalanceSheet','TaiwanStockCashFlowsStatement'])
@pytest.mark.parametrize('operation,expected',[
 (('twse_official','FinMind TWSE official'),'twse_official'),
 (('financial_statements','FinMind financial statement fallback'),'financial_statements'),
 (('twse_official','unrelated callback'),'financial_statements'),
 (None,'financial_statements'),
])
def test_sdk_receipt_uses_actual_operation_without_double_counting(monkeypatch,dataset,operation,expected):
 from contextlib import nullcontext
 events=[];calls=[]
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 def send(self,request,*a,**kw):
  calls.append(1);r=requests.Response();r.status_code=200;r.request=request;r._content=b'original';r._content_consumed=True;return r
 monkeypatch.setattr(requests.Session,'send',send);s=requests.Session();observe_loader(SimpleNamespace(_FinMindApi__session=s))
 req=requests.Request('GET','https://api.finmindtrade.com/api/v4/data',params={'dataset':dataset,'data_id':'2356','token':'PRIVATE'}).prepare()
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='finmind-operation'):
  with source_operation(*operation)if operation else nullcontext():result=s.send(req)
 assert result.content==b'original' and len(calls)==1 and len(events)==1
 e=events[0];assert e['source']==expected and e['provider']=='FinMind native HTTP'
 assert e['record_count']==0 and e['event_kind']=='http_transport_receipt'
 assert 'PRIVATE'not in str(events) and 'token'not in str(events)
 assert e['component_statuses'][dataset]['dataset']==dataset


def test_monthly_revenue_is_not_relabelled_by_outer_official_operation(monkeypatch):
 from finmind_transport_receipts import _record
 import time
 events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
 s=requests.Session();req=requests.Request('GET','https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockMonthRevenue&data_id=2356').prepare();r=requests.Response();r.status_code=200;r.request=req;r._content=b'original';r._content_consumed=True
 with correlation_scope(replace=True,ticker='2356.TW',fetch_id='finmind-operation'):
  with source_operation('twse_official','FinMind TWSE official'):_record(s,req,r,time.monotonic())
 assert len(events)==1 and events[0]['source']=='monthly_revenue'
