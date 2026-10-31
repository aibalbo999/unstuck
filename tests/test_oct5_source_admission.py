"""Regression cases are saved Oct5 inputs, never new model calls or historical writes."""
from copy import deepcopy
from datetime import datetime,date
import gzip,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from market_evidence_policy import completed_evidence_session,session_cache_scope
from official_response_evidence import archive_response,read_response
from report_source_admission import institutional_admission,report_source_admission
from reporting.trade_price_grid import proposed_order_contract,grid_assessment,execution_rows
F=Path(__file__).parent/'fixtures';CASES=json.loads((F/'oct5_saved_source_cases.json').read_text())
@pytest.fixture
def archive(monkeypatch,tmp_path):
 import runtime_paths
 monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:SimpleNamespace(cache_dir=tmp_path));return tmp_path

def official_value():
 from official_institutional_source import _parse_report,_url
 body=(F/'oct5_t86_raw.json').read_bytes();row=_parse_report(json.loads(body),'TWSE','2026-10-05')['rows']['2330'];proof=archive_response(body,source_url=_url('TWSE','2026-10-05'),retrieved_at='2026-10-06T00:49:03.430778+00:00')
 return {'latest_date':'2026-10-05','daily_category_observations':[{'date':'2026-10-05','category':k,'net_buy_shares':row[k],'unit':'shares','source':'TWSE T86'} for k in ('foreign','investment_trust','dealer')],'latest_official_observation':{'date':'2026-10-05','market':'TWSE','ticker':'2330.TW','raw_evidence':proof}}
@pytest.mark.parametrize('moment,expected',[('2026-10-05T13:38:11+08:00','2026-10-02'),('2026-10-05T22:29:59+08:00','2026-10-02'),('2026-10-05T22:30:00+08:00','2026-10-05'),('2026-10-06T08:00:00+08:00','2026-10-05')])
def test_maturity_boundary(moment,expected):assert completed_evidence_session(datetime.fromisoformat(moment))==expected

@pytest.mark.parametrize('moment,expected',[('2026-10-05T13:38:11+08:00',('2026-10-02','post_cutoff')),('2026-10-05T22:29:59+08:00',('2026-10-02','post_cutoff')),('2026-10-05T22:30:00+08:00',('2026-10-05','post_cutoff'))])
def test_session_cache_scope_uses_publication_maturity_boundary(moment,expected):
 assert session_cache_scope(datetime.fromisoformat(moment))==expected

def test_saved_cases_source_gate_and_correct_1301_sma_order():
 from evidence_exit_gate import evaluate_report_evidence
 for case in CASES:
  before=deepcopy(case);result=report_source_admission(case['data'],case['rerun_context']['parsed']['trade_setup']);assert not result['eligible'] and 'executable_price_grid_not_verified' in result['blockers'];gate=evaluate_report_evidence('原保存資料診斷',case);assert gate['verdict']=='rejected' and all(gate['source_admission'][k]==result[k] for k in ('eligible','institutional','price','price_grid','order_gate_applicable','actionable')) and set(result['blockers'])<=set(gate['source_admission']['blockers']) and set(result['source_warnings'])<=set(gate['source_admission']['source_warnings']) and 'price_reference_checks' in gate['source_admission'] and case==before
 t=next(x for x in CASES if x['data']['ticker']=='1301.TW')['data']['technical_indicators'];assert [t['sma_5'],t['sma_10'],t['sma_20']]==pytest.approx([67.26,65.83,65.24],abs=1e-5);assert t['sma_5']>t['sma_10']>t['sma_20']
@pytest.mark.parametrize('ticker,stop',[('3014.TW','136'),('1301.TW','65.2'),('2330.TW','2450')])
def test_real_levels_separate_legal_proposal_recalculates_risk(ticker,stop):
 case=deepcopy(next(x for x in CASES if x['data']['ticker']==ticker));before=deepcopy(case);setup=case['rerun_context']['parsed']['trade_setup'];p=proposed_order_contract(case['data'],setup);assert p['proposed_levels']['stop_loss']==stop and not p['approved'] and not p['actionable'];assert p['recomputed_execution']['worst_case_risk_reward'] is not None;assert grid_assessment(case['data'],p['proposed_levels'])['status']=='grid_aligned_analysis_levels' and case==before
 if ticker=='2330.TW':assert p['proposed_levels']['entry_zone']=='2510-2550'
 assert '不自動核准' in execution_rows(case['data'],setup)[-1]['value']
def test_missing_6715_metadata_is_unchecked_not_valid():
 r=grid_assessment({'ticker':'6715.TW'},{'entry_zone':'450','target_price':'500','stop_loss':'440'});assert r['status']=='unverified' and r['checked_levels']==r['invalid_levels']==[] and r['instrument_type'] is None

def test_real_official_raw_positive_and_150k_conflict(archive):
 v=official_value();r=institutional_admission(v,'2026-10-05');assert r['eligible'] and not r['finality_guaranteed'];v['daily_category_observations'][0]['net_buy_shares']-=150000;assert institutional_admission(v,'2026-10-05')['reason']=='primary_official_latest_categories_mismatch'
def test_provisional_corrupt_and_outside_archive_fail_closed(archive):
 v=official_value();p=v['latest_official_observation']['raw_evidence'];p['retrieved_at']='2026-10-05T10:08:00+00:00';assert institutional_admission(v,'2026-10-05')['reason']=='official_observation_is_provisional';p['retrieved_at']='2026-10-06T00:49:03+00:00';Path(p['raw_response_path']).write_bytes(gzip.compress(b'changed'));assert institutional_admission(v,'2026-10-05')['reason']=='official_raw_evidence_invalid';p['raw_response_path']='/private/not-an-archive'
 with pytest.raises(ValueError,match='outside'):read_response(p)
def test_phase_cache_keys_roll(monkeypatch):
 import data_fetch.market_sources.twse_session_observation as s
 import market_evidence_policy as p
 phase=['provisional'];keys=[];monkeypatch.setattr(p,'acquisition_phase',lambda *a:phase[0])
 def fake(key,fetch,**kw):keys.append((key,kw['freshness_seconds']));return None,{'error_kind':'test-unavailable'}
 monkeypatch.setattr(s,'shared_fetch',fake);s.official_observation('2330.TW','2026-10-05');phase[0]='post_cutoff';s.official_observation('2330.TW','2026-10-05');assert keys==[('report-official-session-ohlcv:v4:2026-10-05:provisional',300),('report-official-session-ohlcv:v4:2026-10-05:post_cutoff',21600)]
def test_whole_cache_rechecks_current_date_and_raw_proof(monkeypatch):
 import data_fetch.yfinance_cache_gate as g
 monkeypatch.setattr(g,'REQUIRED_DATA_SCHEMA_FIELDS',[]);c={'ticker':'1301.TW','data_schema_version':g.DATA_SCHEMA_VERSION,'daily_market_data':{'bars':[{'date':'2026-10-02'}],'as_of':'2026-10-02','price_basis_contract':'market_price_basis.v2','history_query':{'expected_completed_session':'2026-10-02'}}}
 def check():return g.build_fresh_cache_payload('1301.TW',c,assess_cached=lambda *a:(True,{}),append_cache_audit=lambda *a,**kw:pytest.fail('old payload approved'),now_epoch=datetime.fromisoformat('2026-10-06T08:00:00+08:00').timestamp())
 r,stale,_=check();assert r is None and stale==['market_data'];c['daily_market_data']['as_of']='2026-10-05';c['daily_market_data']['history_query']['expected_completed_session']='2026-10-05';r,stale,_=check();assert r is None and set(stale)=={'market_data','institutional_trading'}
def test_explicit_backtest_end_excludes_provisional_day():
 import pandas as pd
 from market_price_history import fetch_backtest_bars
 calls=[]
 class Stock:
  def history(self,**kw):calls.append(kw);return pd.DataFrame({'Open':[10],'High':[11],'Low':[9],'Close':[10]},index=pd.to_datetime(['2026-10-02']))
 rows=fetch_backtest_bars('2371.TW',date(2026,9,17),date(2026,10,5),ticker_factory=lambda _:Stock(),moment=datetime.fromisoformat('2026-10-05T13:38:11+08:00'));assert calls[0]['end']=='2026-10-03' and rows[-1]['date']=='2026-10-02' and rows[-1]['observation_provenance']['finality_verified'] is False

def test_maturity_source_requires_independent_raw_publication_and_price_match(monkeypatch):
 import maturity_source_admission as m
 bars=[{'date':'2026-10-05','open':31.5,'high':31.5,'low':30.15,'close':30.20,'observation_provenance':{'official_observation':{'open':31.5,'high':31.5,'low':30.15,'close':30.15}}}]
 assert not m.assess_maturity_source(bars,'2371.TW','2026-10-05')['eligible']
 monkeypatch.setattr(m,'price_admission',lambda *a:{'eligible':True,'raw_evidence':{'status':'isolated proof fixture'}})
 mismatch=m.assess_maturity_source(bars,'2371.TW','2026-10-05');assert mismatch['reason']=='maturity_provider_official_price_mismatch' and mismatch['field']=='close'
 bars[0]['close']=30.15;passed=m.assess_maturity_source(bars,'2371.TW','2026-10-05');assert passed['eligible'] and not passed['finality_guaranteed'] and not passed['all_historical_bars_verified']
