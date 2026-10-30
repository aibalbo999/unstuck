from datetime import date
from copy import deepcopy
import json
import pytest
from data_fetch.market_sources import ncc_mobile_peer_cohort as s
TODAY=date(2026,10,30)


def data():
 rows=[]
 for year in range(2023,2027):
  for month in range(1,13):
   if (year,month)>(2026,9):break
   for _,legal,_ in s.IDENTITIES.values():
    rows.append(dict(ym=(year-1911)*100+month,cname=legal,num1=100,num2=60,num21=50,num22=10,num3=40,num31=30,num32=10))
 return rows


def test_complete_monthly_original_yields_three_dated_operator_leads():
 out=s.parse_members(json.dumps(data(),ensure_ascii=False).encode(),today=TODAY)
 assert out['period_end']=='2026-09-30' and len(out['members'])==3
 assert out['membership_effective_date_verified']is False

@pytest.mark.parametrize('change',[
 lambda r:r[-1].update(ym=11513),lambda r:r[-1].update(ym=11511),
 lambda r:r[-1].update(num1=True),lambda r:r[-1].update(num1=99),
 lambda r:r[-1].update(cname='遠傳子公司股份有限公司'),
 lambda r:r.append(deepcopy(r[-1])),lambda r:r[-1].update(extra='unbound'),
 lambda r:r.pop(),lambda r:r[-1].update(num21=-1),
 lambda r:r[-1].update(num31=29),lambda r:r[-1].update(num2=59)])
def test_unknown_or_incomplete_latest_membership_is_rejected(change):
 rows=data();change(rows)
 with pytest.raises(ValueError):s.parse_members(json.dumps(rows,ensure_ascii=False).encode(),today=TODAY)


def test_duplicate_json_fields_and_expired_or_future_month_fail_closed():
 raw=json.dumps(data(),ensure_ascii=False).encode()
 with pytest.raises(ValueError):s.parse_members(raw.replace(b'"ym":',b'"ym":11509,"ym":',1),today=TODAY)
 with pytest.raises(ValueError):s.parse_members(raw,today=date(2026,12,2))
 with pytest.raises(ValueError):s.parse_members(raw,today=date(2026,9,29))

from datetime import datetime
from zoneinfo import ZoneInfo
import time
from test_shared_provider_cache import memory_cache
NOW=datetime(2026,10,30,15,20,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()


def issuer_rows():
 rows=[{'公司代號':str(n),'公司名稱':f'測試{n}股份有限公司','公司簡稱':f'測{n}','出表日期':'1151030','營利事業統一編號':str(20000000+n),'網址':'https://example.com'}for n in range(1000,1800)]
 for ticker,(short,legal,ubn)in s.IDENTITIES.items():
  rows.append({'公司代號':ticker[:4],'公司名稱':legal,'公司簡稱':short,'出表日期':'1151030','營利事業統一編號':ubn,'網址':'https://example.com'})
 return rows


def master_rows():return [{'stock_id':t[:4],'stock_name':short,'type':'twse','date':TODAY.isoformat(),'industry_category':'通信網路業'}for t,(short,_,_)in s.IDENTITIES.items()]


def harness(monkeypatch,*,roster=None):
 from official_response_evidence import archive_response
 from cache_store import set_cache_json
 from hashlib import sha256
 from data_fetch.market_sources.ncc_mobile_peer_transport import MobileHttp
 monkeypatch.setattr(time,'time',lambda:NOW)
 raw=json.dumps(issuer_rows()if roster is None else roster,ensure_ascii=False).encode()
 archive_response(raw,source_url=s.URLS['.TW'],retrieved_at=NOW,http_status=None,evidence_kind=s.SHARED_KIND)
 value=s.parse_roster(raw,'.TW');set_cache_json('shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest(),
  {'value':value,'fetched_at_epoch':NOW,'fresh_until_epoch':NOW+86400,'retained_until_epoch':NOW+86400},ttl_seconds=86400)
 calls=[];body=json.dumps(data(),ensure_ascii=False).encode()
 def download(self,diagnostic):
  calls.append(s.SOURCE_URL)
  parts={'process_started':True,'headers':b'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n','body':body,
   'metadata':json.dumps({'http_code':200,'url_effective':s.SOURCE_URL,'ssl_verify_result':0,'proxy_used':0,'num_redirects':0,'size_download':len(body)}).encode()}
  return self._consume(parts,0,None,diagnostic)
 monkeypatch.setattr(MobileHttp,'_download',download)
 return calls


def test_normal_membership_fetch_keeps_shared_issuer_http_unknown_and_warm_http_zero(monkeypatch):
 calls=harness(monkeypatch);a=s.get_candidates('2412.TW',master_rows(),today=TODAY);b=s.get_candidates('2412.TW',master_rows(),today=TODAY)
 assert a['status']=='success'and [r['ticker']for r in a['candidates']]==['3045.TW','4904.TW']
 assert calls==[s.SOURCE_URL]and a['http_request_count']==1 and b['http_request_count']==0 and b['cache_hit']is True
 first=a['candidates'][0][s.RECEIPT_KEY];second=b['candidates'][0][s.RECEIPT_KEY]
 assert first==second and first[s.URLS['.TW']]['http_status']is None and first[s.URLS['.TW']]['http_status_observed']is False
 assert s.verified_candidates(a['candidates'],'2412.TW',today=TODAY)
 assert all(r['numeric_comparability_verified']is False and r['business_comparability_verified_current']is False for r in a['candidates'])

@pytest.mark.parametrize('change',[
 lambda rs:rs[0].update(name='其他公司'),lambda rs:rs[0].update(ticker='2330.TW'),
 lambda rs:rs[0].update(membership_period_end='2026-10-31'),lambda rs:rs[0].update(numeric_comparability_verified=True),
 lambda rs:rs[0].update(business_comparability_verified_current=True),lambda rs:rs.append(deepcopy(rs[0])),
 lambda rs:rs[0][s.RECEIPT_KEY][s.SOURCE_URL].update(retrieved_at=NOW+1),
 lambda rs:rs[0][s.RECEIPT_KEY][s.SOURCE_URL].update(fresh_until_epoch=NOW+1801)])
def test_membership_verification_rejects_changed_receipts_names_periods_and_comparability(monkeypatch,change):
 harness(monkeypatch);rows=s.get_candidates('2412.TW',master_rows(),today=TODAY)['candidates'];assert rows;change(rows)
 assert not s.verified_candidates(rows,'2412.TW',today=TODAY)


def test_original_expiry_after_quote_work_cannot_be_extended(monkeypatch):
 harness(monkeypatch);rows=s.get_candidates('2412.TW',master_rows(),today=TODAY)['candidates'];assert rows
 monkeypatch.setattr(time,'time',lambda:NOW+1800)
 assert not s.verified_candidates(rows,'2412.TW',today=TODAY)

@pytest.mark.parametrize('field,value',[('公司名稱','中華電信子公司股份有限公司'),('公司簡稱','中華電信'),('營利事業統一編號','12345678'),('出表日期','1151010')])
def test_complete_issuer_master_must_bind_target_exactly(monkeypatch,field,value):
 rows=issuer_rows();next(r for r in rows if r['公司代號']=='2412')[field]=value;calls=harness(monkeypatch,roster=rows)
 assert not s.get_candidates('2412.TW',master_rows(),today=TODAY)['candidates']and not calls


def test_stale_or_ambiguous_stock_master_never_starts_new_membership_fetch(monkeypatch):
 calls=harness(monkeypatch);rows=master_rows();rows[0]['date']='2026-10-01'
 assert not s.get_candidates('2412.TW',rows,today=TODAY)['candidates']and not calls


def metrics_harness(monkeypatch,*,changes=None):
 import pandas as pd
 from data_fetch.market_sources import peers
 calls=harness(monkeypatch);rows=master_rows()
 rows.extend(dict(stock_id=str(n),stock_name=f'設備{n}',type='twse',date=TODAY.isoformat(),industry_category='通信網路業')for n in range(2413,2425))
 monkeypatch.setattr(peers,'load_peer_stock_master',lambda:rows);monkeypatch.setattr(peers,'_today',lambda:TODAY)
 quotes=[]
 class Stock:
  def __init__(self,ticker):
   quotes.append(ticker)
   self.info={'symbol':ticker,'quoteType':'EQUITY','industry':'Telecom Services'if ticker in s.IDENTITIES else'Communication Equipment',
    'trailingPE':15,'priceToBook':2,'priceToSalesTrailing12Months':1.5,'grossMargins':.3,'operatingMargins':.2,'profitMargins':.1,'returnOnEquity':.15,'dividendYield':.03}
   if changes and ticker=='3045.TW':self.info.update(changes)
  @property
  def financials(self):return pd.DataFrame()
  @property
  def balance_sheet(self):return pd.DataFrame()
 monkeypatch.setattr(peers.yf,'Ticker',Stock)
 return peers,calls,quotes


def run_metrics(peers):return peers.fetch_dynamic_peer_metrics_with_diagnostics('2412.TW','中華電','Communication Services','Telecom Services',{'ticker':'2412.TW','stock_id':'2412','official_name':'中華電','instrument_type':'EQUITY'})


def test_dated_operator_leads_recover_two_metrics_inside_original_ten_attempt_budget(monkeypatch):
 peers,calls,quotes=metrics_harness(monkeypatch);result=run_metrics(peers)
 assert [r['ticker']for r in result['peers']]==['3045.TW','4904.TW']
 assert {'3045.TW','4904.TW'}<=set(quotes[:5])and len(quotes)==10
 assert result['audit']['candidate_attempt_count']==10 and result['audit']['usable_count']==2
 assert calls==[s.SOURCE_URL]and result['audit']['official_ncc_candidate_status']=='success'
 from prompt_builder import format_data_for_prompt
 payload={'ticker':'2412.TW','company_name':'中華電','dynamic_peer_metrics':result['peers']};prompt=format_data_for_prompt(payload)
 structured,_=json.JSONDecoder().raw_decode(prompt[prompt.index('{'):]);assert structured['peer_context']['dynamic_peer_metrics']==[]
 assert s.verified_candidates(result['peers'],'2412.TW',today=TODAY)

@pytest.mark.parametrize('field,value',[('symbol',None),('symbol','2330.TW'),('quoteType',None),('quoteType','ETF'),('industry',None),('industry','Communication Equipment')])
def test_membership_never_bypasses_live_quote_identity_and_industry(monkeypatch,field,value):
 peers,_,_=metrics_harness(monkeypatch,changes={field:value});result=run_metrics(peers)
 assert [r['ticker']for r in result['peers']]==['4904.TW']and result['audit']['usable_count']==1


def test_originals_expiring_during_metrics_are_removed_without_retry(monkeypatch):
 peers,_,_=metrics_harness(monkeypatch);original=peers.verified_ncc_candidates
 def expired(records,ticker,*,today):
  monkeypatch.setattr(time,'time',lambda:NOW+1800)
  return original(records,ticker,today=today)
 monkeypatch.setattr(peers,'verified_ncc_candidates',expired);result=run_metrics(peers)
 assert result['peers']==[]and result['audit']['official_ncc_candidate_status']=='originals_expired_or_unverified_after_metrics'


def test_missing_historical_split_is_unknown_without_invalidating_complete_latest_month():
 rows=data();rows[0]['num21']='';rows[0]['num22']='';rows[0]['num31']='';rows[0]['num32']=''
 result=s.parse_members(json.dumps(rows,ensure_ascii=False).encode(),today=TODAY)
 assert result['historical_missing_subcounts']==4 and result['period_end']=='2026-09-30'
 assert rows[0]['num21']==''

@pytest.mark.parametrize('field',['num1','num2','num3','num21','num22','num31','num32'])
def test_latest_month_never_accepts_missing_or_imputed_counts(field):
 rows=data();rows[-1][field]=''
 with pytest.raises(ValueError):s.parse_members(json.dumps(rows,ensure_ascii=False).encode(),today=TODAY)

@pytest.mark.parametrize('enabled',[False,True])
def test_new_native_observations_respect_request_flag_and_actual_source_scope(monkeypatch,enabled):
 from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
 from data_fetch.types import FetchRequest
 from provider_correlation import correlation_scope
 import provider_sla
 peers,_,_=metrics_harness(monkeypatch);observed=[]
 monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:observed.extend(rows))
 payload={'ticker':'2412.TW','company_name':'中華電','sector':'Communication Services','industry':'Telecom Services','company_identity':{'ticker':'2412.TW','stock_id':'2412','official_name':'中華電','instrument_type':'EQUITY'}}
 with correlation_scope(replace=True,ticker='2412.TW',fetch_id='isolated-flow'):
  result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('2412.TW',record_provider_sla=enabled),{'data':payload})
 assert len(result.value)==2
 assert len(observed)==int(enabled)
 if enabled:assert observed[0]['event_kind']=='http_transport_receipt'and observed[0]['record_count']==0 and observed[0]['source']=='dynamic_peer_metrics'


def test_final_verification_time_is_inside_the_same_total_deadline(monkeypatch):
 harness(monkeypatch);clock=[100.];monkeypatch.setattr(time,'monotonic',lambda:clock[0]);original=s.verified_candidates
 def delayed(*a,**kw):
  valid=original(*a,**kw);clock[0]+=13;return valid
 monkeypatch.setattr(s,'verified_candidates',delayed)
 result=s.get_candidates('2412.TW',master_rows(),today=TODAY)
 assert not result['candidates']and result['status']=='ncc_membership_unavailable'


def test_statistics_month_must_be_finished_at_acquisition():
 raw=json.dumps(data(),ensure_ascii=False).encode()
 with pytest.raises(ValueError):s.parse_members(raw,today=date(2026,9,30))
 assert s.parse_members(raw,today=date(2026,10,1))['period_end']=='2026-09-30'

@pytest.mark.parametrize('field,value',[('ticker','2330.TW'),('stock_id','2330'),('official_name','中華電信子公司'),('instrument_type','ETF'),('legal_name','其他公司股份有限公司'),('official_ubn','12345678')])
def test_conflicting_parent_identity_never_starts_new_cohort_request(monkeypatch,field,value):
 peers,calls,_=metrics_harness(monkeypatch)
 identity={'ticker':'2412.TW','stock_id':'2412','official_name':'中華電','instrument_type':'EQUITY',field:value}
 peers.fetch_dynamic_peer_metrics_with_diagnostics('2412.TW','中華電','Communication Services','Telecom Services',identity)
 assert not calls
