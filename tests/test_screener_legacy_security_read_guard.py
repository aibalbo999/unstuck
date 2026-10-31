from copy import deepcopy
import pytest
from screener_signal_dimensions import separate_signals

def legacy():
 return {'ticker':'2002.TW','category':'institutional_accumulation','categories':['institutional_accumulation'],'reason':'外資買超938張，投信買超209張','metrics':{'foreign_net_buy_shares':937936,'investment_trust_net_buy_shares':209000,'latest_volume':51310,'close':37.45,'flow_source':'TWSE Free API','price_source':'TWSE Free API','price_source_url':'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20261030&type=ALL&response=json','latest_volume_unit':'shares','flow_observation_date':'2026-10-30','volume_observation_date':'2026-10-30'}}

def qualified():
 r=legacy();r['metrics'].update(close=19.25,latest_volume=27995185,source_security_code='2002',source_security_policy='twse-exact-source-code:v1',flow_security_code='2002',flow_security_policy='twse-exact-source-code:v1');return r

def test_legacy_view_cannot_reuse_collapsed_security_numbers_or_mutate_input():
 old=legacy();before=deepcopy(old);r=separate_signals(old)
 assert r['metrics']['normalized_flow_pct'] is None
 assert r['metrics']['close'] is None and r['metrics']['latest_volume'] is None
 assert r['metrics']['foreign_net_buy_shares'] is None
 assert r['source_security_identity_status']=='unverified'
 assert r['unverified_security_observations']['latest_volume']==51310
 assert 'institutional_accumulation' not in r['categories'] and old==before
 assert separate_signals(r)==r

def test_exactly_qualified_fresh_observation_keeps_value_and_ratio():
 r=separate_signals(qualified());assert r['metrics']['normalized_flow_pct']==pytest.approx(1146936/27995185*100)
 assert r['metrics']['close']==19.25 and r['source_security_identity_status']=='verified_exact_code'
 assert r['actionable'] is False

@pytest.mark.parametrize('field,value',[('source_security_code','2002A'),('flow_security_code','2002A'),('source_security_policy','unknown'),('flow_security_policy','unknown')])
def test_marker_cannot_bind_another_security_or_unknown_policy(field,value):
 r=qualified();r['metrics'][field]=value;r=separate_signals(r)
 assert r['metrics']['normalized_flow_pct'] is None and r['source_security_identity_status']=='unverified'

def test_non_twse_source_keeps_existing_separate_dimension_semantics():
 r=legacy();r['metrics'].update(flow_source='FinMind',price_source='FinMind');r['metrics'].pop('price_source_url')
 assert separate_signals(r)['metrics']['normalized_flow_pct']==pytest.approx(1146936/51310*100)

def test_unverified_legacy_observation_cannot_overwrite_existing_watchlist(monkeypatch):
 import market_screener
 writes=[];monkeypatch.setattr(market_screener.watchlist_service,'upsert_watchlist_item',lambda item:writes.append(item))
 old=legacy();before=deepcopy(old);r=market_screener.import_candidates_to_watchlist([old])
 assert not writes and r['imported_count']==0 and r['errors'] and old==before

def test_existing_watchlist_read_is_guarded_without_rewriting_storage(monkeypatch):
 import market_screener
 old=legacy();item={'ticker':'2002.TW','pipeline':'v4','tags':['auto_screener'],'trigger_source':'daily_screener','triggers':[{'type':'daily_screener',**{k:v for k,v in old.items() if k!='ticker'}}]};before=deepcopy(item)
 monkeypatch.setattr(market_screener.watchlist_service,'list_watchlist_with_report_alerts',lambda *a,**kw:{'items':[item]})
 r=market_screener.list_auto_screener_watchlist(sync_metadata=False)
 assert r['items'] and r['items'][0]['metrics']['close'] is None and item==before


def test_legacy_daily_trigger_does_not_claim_match_or_borrow_data_ticker():
 from watchlist_triggers import evaluate_watchlist_triggers
 r=legacy();item={'ticker':'2002.TW','pipeline':'v4','triggers':[{'type':'daily_screener',**{k:v for k,v in r.items() if k!='ticker'}}]}
 assert evaluate_watchlist_triggers(item,{'ticker':'2002.TW'},evaluation_date='2026-10-31')[0]['matched'] is False
 r=qualified();item['triggers'][0]['metrics']=r['metrics'];assert evaluate_watchlist_triggers(item,{'ticker':'2002.TW'},evaluation_date='2026-10-31')[0]['matched'] is True
 item['triggers'][0]['metrics']={**r['metrics'],'source_security_code':'2891','flow_security_code':'2891'}
 assert evaluate_watchlist_triggers(item,{'ticker':'2891.TW'},evaluation_date='2026-10-31')[0]['matched'] is False

def test_guard_keeps_existing_historical_matched_event_unchanged(monkeypatch,tmp_path):
 import watchlist_service,watchlist_trigger_store,watchlist_store
 import sqlite3
 from watchlist_triggers import evaluate_watchlist_triggers
 monkeypatch.setattr(watchlist_service,'WATCHLIST_DB_PATH',str(tmp_path/'watchlist.sqlite3'))
 monkeypatch.setattr(watchlist_service,'WATCHLIST_PATH',tmp_path/'watchlist.json');watchlist_service.reset_watchlist_store_for_tests();watchlist_service._sync_store_config()
 r=legacy();item={'ticker':'2002.TW','pipeline':'v4','triggers':[{'type':'daily_screener',**{k:v for k,v in r.items() if k!='ticker'}}]}
 event=evaluate_watchlist_triggers(item,{'ticker':'2002.TW'},evaluation_date='2026-10-31')[0]
 historical={**event,'matched':True,'message':'original historical observation','metrics':r['metrics']}
 assert watchlist_trigger_store.record_trigger_event(historical)['inserted']
 with sqlite3.connect(str(tmp_path/'watchlist.sqlite3')) as db:before=db.execute('select * from watchlist_trigger_events').fetchall()
 assert event['matched'] is False and not watchlist_trigger_store.record_trigger_event(event)['inserted']
 with sqlite3.connect(str(tmp_path/'watchlist.sqlite3')) as db:assert db.execute('select * from watchlist_trigger_events').fetchall()==before
 watchlist_service.reset_watchlist_store_for_tests()


@pytest.mark.parametrize('shape',['legacy','malformed'])
def test_old_or_malformed_cache_uses_normal_acquisition_without_mutating_old_value(monkeypatch,shape):
 from datetime import date
 import pandas as pd
 import market_screener
 from test_twse_dated_daily_fallback import source
 provider,calls=source();flow=[]
 for name in ('Foreign_Investor','Investment_Trust'):
  flow.extend(provider._institutional_records_from_payload({'date':'20261002','data':[[1,'1301','台塑','1000','0']]},name,date(2026,10,2)))
 provider.fetch_institutional_frame=lambda day:pd.DataFrame(flow)
 old={'success':True,'candidates':[legacy()] if shape=='legacy' else None};before=deepcopy(old);writes=[]
 monkeypatch.setattr(market_screener,'get_cache_json',lambda key:old)
 monkeypatch.setattr(market_screener,'set_cache_json',lambda key,value,**kw:writes.append((key,deepcopy(value),kw)))
 monkeypatch.setattr(market_screener,'annotate_watchlist_status',lambda rows:rows)
 result=market_screener.scan_taiwan_market(scan_date=date(2026,10,2),data_source=provider,use_cache=True,top_n=1)
 assert calls and result['cache']['hit'] is False and old==before
 assert {r['ticker'] for r in result['candidates']}=={'1301.TW'}
 assert result['candidates'][0]['metrics']['close']==68.3
 assert result['candidates'][0]['source_security_identity_status']=='verified_exact_code'
 assert writes and writes[0][0].startswith('screener-observations-v5-exact-security:')
 assert any(w['code']=='cached_security_identity_unverified' for w in result['warnings'])


def test_unverified_view_removes_dependent_tags_without_erasing_original():
 old=legacy();old['tags']=['auto_screener','institutional_accumulation','technical_heat','user_label'];before=deepcopy(old)
 result=separate_signals(old)
 assert result['tags']==['auto_screener','user_label']
 assert result['unverified_security_observations']['tags']==before['tags']
 assert old==before and separate_signals(result)==result


@pytest.mark.parametrize('section,key',[('technical','rsi_max'),('technical','macd_min'),('institutional','total_net_buy_shares_min')])
def test_missing_metrics_cannot_pass_zero_or_upper_bound_filters(section,key):
 from market_screener_candidate_query import filter_candidates
 row=separate_signals(legacy())
 row['metrics'].update(rsi_14=None,macd=None,total_net_buy_shares=None)
 assert filter_candidates([row],{section:{key:0}})==[]

def test_guarded_categories_do_not_match_old_signal_or_lose_unknown_category():
 from market_screener_candidate_query import filter_candidates
 row=separate_signals(legacy())
 assert not filter_candidates([row],{'categories':['institutional_accumulation']})
 assert filter_candidates([row],{'categories':['unverified_source']})==[row]


@pytest.mark.parametrize('value',[None,'','--',True,float('nan'),float('inf')])
def test_metric_filter_rejects_unknown_or_nonfinite_but_not_zero(value):
 from market_screener_candidate_query import filter_candidates
 row={'ticker':'2002.TW','metrics':{'rsi_14':value}}
 assert filter_candidates([row],{'technical':{'rsi_max':90}})==[]
 row['metrics']['rsi_14']=0
 assert filter_candidates([row],{'technical':{'rsi_max':90}})==[row]
