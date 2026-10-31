from copy import deepcopy
import json,sqlite3
import pytest
from provider_observation_details import observation_details

def entry():
 return {'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','event_kind':'aggregate','status':'degraded_enrichment','record_count':1,'quality_status':'partial_metrics','coverage_status':'partial','candidate_diagnostics':[{'ticker':'2007.TW','metrics_status':'partial','comparison_status':'business_industry_matched','missing_metrics':['pe_ttm'],'acquisition_attempts':[{'provider':'yfinance','status':'success'},{'provider':'FinMind TaiwanStockPER','status':'success','observed_at':'2026-10-30','cache_hit':False}]}]}

def test_current_missing_field_and_provider_outcomes_survive_observation_projection():
 e=entry();before=deepcopy(e);v=observation_details(e)
 assert v['candidate_diagnostics']==e['candidate_diagnostics']
 assert e==before and v['quality_status']=='partial_metrics'

def test_sqlite_round_trip_keeps_partial_failure_and_does_not_invent_success():
 import provider_sla
 from provider_acquisition import get_provider_acquisition_summary
 e=entry();provider_sla.record_source_audit_entries([e])
 with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:v=json.loads(db.execute('select details_json from provider_sla_events').fetchone()[0])
 assert v['candidate_diagnostics'][0]['missing_metrics']==['pe_ttm']
 row=get_provider_acquisition_summary()['sources'][0]
 assert row['fetch_attempts']==1 and row['fetched_count']==0 and row['degraded_count']==1

@pytest.mark.parametrize('field,value',[('source','recent_catalysts'),('provider','untrusted')])
def test_unrelated_source_cannot_add_peer_diagnostics(field,value):
 e=entry();e[field]=value;assert 'candidate_diagnostics'not in observation_details(e)

def test_diagnostics_are_bounded_typed_and_never_keep_body_credentials_or_query():
 e=entry();good=deepcopy(e['candidate_diagnostics'][0]);good.update(api_key='SECRET',response_body='SECRET',reported_industry='SECRET')
 good['missing_metrics']=['pe_ttm','SECRET','pe_ttm'];good['acquisition_attempts']=[{'provider':'yfinance','status':'success','url':'https://example.com/?token=SECRET','headers':{'Authorization':'SECRET'}}]*100
 e['candidate_diagnostics']=[good]*100+[{'ticker':'SECRET','metrics_status':'partial','missing_metrics':['pe_ttm']}]
 v=observation_details(e)['candidate_diagnostics'];assert len(v)==10 and all(len(r['acquisition_attempts'])<=6 for r in v)
 assert 'SECRET'not in json.dumps(v) and all(r['missing_metrics']==['pe_ttm']for r in v)

def test_persisted_gap_rows_identify_selected_and_rejected_candidates(monkeypatch):
 from data_fetch.market_sources import peers
 candidates=[{'ticker':str(c)+'.TW','name':'bank','comparison_status':'industry_candidate_only'}for c in range(2801,2807)]
 monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[])
 monkeypatch.setattr(peers,'resolve_legacy_peer_candidates',lambda *a,**k:(candidates,{'selection_status':'selected'}))
 class Stock:
  def __init__(self,symbol):self.symbol=symbol
  @property
  def info(self):return {'symbol':self.symbol,'quoteType':'EQUITY','industry':'Insurance - Life'if self.symbol=='2806.TW'else'Banks - Regional','trailingPE':12.,'priceToBook':1.2,'operatingMargins':.1,'profitMargins':.1,'returnOnEquity':.1}
 monkeypatch.setattr(peers.yf,'Ticker',Stock)
 result=peers.fetch_dynamic_peer_metrics_with_diagnostics('2880.TW','target','Financial Services','Banks - Regional',{})
 chosen={r['ticker']for r in result['peers']};rows=result['audit']['candidate_diagnostics']
 assert chosen and any(r['ticker']not in chosen for r in rows)
 assert all(r['selected']==(r['ticker']in chosen)for r in rows)
 e={'source':'dynamic_peer_metrics','provider':'FinMind/yfinance',**result['audit']}
 projected=observation_details(e)['candidate_diagnostics']
 assert all(r['selected']==(r['ticker']in chosen)for r in projected)
