"""Recover only institutional observations after their existing evidence cutoff."""
import asyncio,json,time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import pytest
from fastapi import HTTPException
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import init_db,events
from storage.report_storage import InMemoryStorage
from data_fetch.provider_base import CallableProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_refresh_service import refresh_report_data_snapshot

NOW=datetime.fromisoformat('2026-10-05T23:00:00+08:00').timestamp()
@pytest.fixture
def fixed(monkeypatch):
    monkeypatch.setattr(time,'time',lambda:NOW)


def observed():
    from official_institutional_source import _parse_report,_url,expected_sessions
    from official_response_evidence import archive_response
    from institutional_observations import summarize_observations
    from report_source_admission import institutional_admission
    from config import INSTITUTIONAL_LOOKBACK_DAYS
    body=(Path(__file__).parent/'fixtures/oct5_t86_raw.json').read_bytes()
    row=_parse_report(json.loads(body),'TWSE','2026-10-05')['rows']['6214']
    days=expected_sessions('6214.TW',NOW,INSTITUTIONAL_LOOKBACK_DAYS)
    records=[{'date':day,'category':category,'net_buy_shares':row[category]if day==days[0]else 100,'unit':'shares','source':'TWSE T86'if day==days[0]else'FinMind TaiwanStockInstitutionalInvestorsBuySell'}for day in days for category in ('foreign','investment_trust','dealer')]
    value=summarize_observations(records,'6214.TW',limit=INSTITUTIONAL_LOOKBACK_DAYS)
    proof=archive_response(body,source_url=_url('TWSE',days[0]),retrieved_at='2026-10-05T14:45:00+00:00',http_status=200)
    value.update(latest_official_observation={'ticker':'6214.TW','market':'TWSE','date':days[0],'raw_evidence':proof},stale=False,cache_hit=False,fetched_at_epoch=NOW-10,coverage_status='available')
    value['latest_session_admission']=institutional_admission(value,days[0]);assert value['latest_session_admission']['eligible']
    audit={'source':'institutional_trading','provider':'FinMind','status':'success','record_count':10,'fetched_at_epoch':NOW-10,'cache_hit':False,'stale':False,'event_kind':'aggregate','http_request_sent':True,'coverage_status':'available','latest_session_admission':deepcopy(value['latest_session_admission'])}
    return value,audit

def report():
    storage=InMemoryStorage();filename,keys,old=saved_report(storage)
    old['data']['company_identity']={'ticker':'6214.TW','stock_id':'6214','instrument_type':'EQUITY','official_name':'精誠'}
    old['data']['institutional_trading']={'latest_date':'2026-10-02','original_limited_observation':True}
    old['source_audit'].append({'source':'institutional_trading','provider':'FinMind','status':'degraded_enrichment','record_count':10,'fetched_at_epoch':NOW-86400,'fetch_id':'old-institutional'})
    old['data']['source_audit']=deepcopy(old['source_audit']);storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    return storage,filename,keys,old

def service(value,audit,calls):
    def acquire(request,context):
        calls.append(request);return ProviderResult('institutional_trading','FinMind',audit['status'],value=deepcopy(value),audit=deepcopy(audit))
    def forbidden(*a,**k):pytest.fail('no full,market or model acquisition is permitted')
    return StockDataService(registry=ProviderRegistry([CallableProvider('institutional_trading','FinMind',acquire),CallableProvider('market_data','forbidden',forbidden)]))

def test_complete_source_only_refresh_preserves_other_sources_and_all_report_gates(fixed,tmp_path):
    init_db();storage,name,keys,old=report();value,audit=observed();calls=[]
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert len(calls)==1 and calls[0].options.force_refresh is False
    assert saved['data']['institutional_trading']==value
    assert response['analysis_text_stale']is True
    assert [a for a in saved['source_audit']if a['source']!='institutional_trading']==[a for a in old['source_audit']if a['source']!='institutional_trading']
    for k in ('current_price','years','revenue_history','peer_discovery_results','earnings_call'):assert saved['data'][k]==old['data'][k]
    for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert saved[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    archive=saved['data']['source_record_archive']
    assert any(x.get('record')==old['data']['institutional_trading']for x in archive)
    assert any(x.get('audit')==old['source_audit'][-1]for x in archive)
    assert any(e['source']=='institutional_trading'for e in events())

@pytest.mark.parametrize('change',[
    lambda v,a:v.update(latest_date='2026-10-02'),
    lambda v,a:v['latest_official_observation'].update(ticker='2330.TW'),
    lambda v,a:v['latest_official_observation'].update(market='TPEX'),
    lambda v,a:v['latest_official_observation']['raw_evidence'].update(retrieved_at='2026-10-05T14:29:59+00:00'),
    lambda v,a:v['latest_official_observation']['raw_evidence'].update(retrieved_at='2026-10-06T00:00:00+00:00'),
    lambda v,a:v['latest_official_observation']['raw_evidence'].update(raw_response_sha256='0'*64),
    lambda v,a:v['daily_category_observations'].pop(),
    lambda v,a:v['daily_category_observations'].__setitem__(0,deepcopy(v['daily_category_observations'][1])),
    lambda v,a:v['daily_category_observations'][0].update(net_buy_shares=True),
    lambda v,a:v['daily_category_observations'][0].update(net_buy_shares=float('nan')),
    lambda v,a:v['daily_category_observations'][0].update(unit='lots'),
    lambda v,a:v.update(total_net_buy_shares=v['total_net_buy_shares']+1),
    lambda v,a:v.update(total_net_buy_shares=True),
    lambda v,a:v.update(window_coverage_status='missing_sessions'),
    lambda v,a:v.update(coverage_status='partial'),
    lambda v,a:v.update(stale=True),
    lambda v,a:a.update(stale=True),
    lambda v,a:a.update(coverage_status='partial'),
    lambda v,a:a.update(record_count=30),
    lambda v,a:a.update(provider='unqualified'),
    lambda v,a:a.update(status='degraded_enrichment'),
    lambda v,a:a.update(fetched_at_epoch=NOW+1),
    lambda v,a:a.update(fetched_at_epoch=NOW-86400*7),
    lambda v,a:a.update(fetched_at_epoch=NOW-100),
])
def test_bad_source_keeps_snapshot_conclusions_and_gate_bytes(fixed,tmp_path,change):
    init_db();storage,name,keys,old=report();value,audit=observed();change(value,audit);calls=[]
    before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as failure:
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    assert failure.value.status_code==502 and len(calls)==1
    assert storage.get_report(keys.data_key).content==before
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'

@pytest.mark.parametrize('change',[
    lambda d:d['company_identity'].update(ticker='2330.TW'),
    lambda d:d['company_identity'].update(stock_id='2330'),
    lambda d:d.update(quote_type='ETF'),
    lambda d:d.update(instrument_type='INDEX'),
    lambda d:d.update(source_record_archive='invalid'),
    lambda d:d.update(data_source_notes=[{}]),
    lambda d:d.update(institutional_trading=[]),
])
def test_conflicting_context_stops_before_provider(fixed,tmp_path,change):
    init_db();storage,name,keys,old=report();change(old['data']);storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    before=storage.get_report(keys.data_key).content;value,audit=observed();calls=[]
    with pytest.raises(HTTPException)as failure:
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    assert failure.value.status_code==400 and not calls and storage.get_report(keys.data_key).content==before

def test_today_provisional_value_still_rejected_before_cutoff(fixed,tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();value,audit=observed();calls=[];before=storage.get_report(keys.data_key).content
    monkeypatch.setattr(time,'time',lambda:datetime.fromisoformat('2026-10-05T22:29:59+08:00').timestamp())
    monkeypatch.setattr('data_freshness_market.market_calendar',lambda *a,**k:{'coverage_status':'available','holidays':set()})
    with pytest.raises(HTTPException)as failure:
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    # A mature previous-session request is allowed, but this fake provider
    # returned today's provisional observation; the merge must reject it.
    assert failure.value.status_code==502 and len(calls)==1
    assert storage.get_report(keys.data_key).content==before

def test_nontrading_weekday_before_cutoff_can_use_last_completed_session(monkeypatch):
    from institutional_source_refresh import institutional_refresh_session
    monkeypatch.setattr(time,'time',lambda:datetime.fromisoformat('2026-10-05T20:00:00+08:00').timestamp())
    monkeypatch.setattr('data_freshness_market.market_calendar',lambda *a,**k:{'coverage_status':'available','holidays':{datetime(2026,10,5).date()}})
    assert institutional_refresh_session('6214.TW')=='2026-10-02'

@pytest.mark.parametrize('ticker',['6214.TW','6152.TWO'])
@pytest.mark.parametrize('moment,expected',[
    ('2026-10-05T20:00:00+08:00','2026-10-02'),
    ('2026-10-05T23:00:00+08:00','2026-10-05'),
    ('2026-10-04T12:00:00+08:00','2026-10-02'),
])
def test_refresh_uses_the_providers_mature_market_session(monkeypatch,ticker,moment,expected):
    from institutional_source_refresh import institutional_refresh_session
    seen=[]
    def calendar(value,**kwargs):
        seen.append(value)
        return {'coverage_status':'available','holidays':set()}
    monkeypatch.setattr(time,'time',lambda:datetime.fromisoformat(moment).timestamp())
    monkeypatch.setattr('data_freshness_market.market_calendar',calendar)
    assert institutional_refresh_session(ticker)==expected
    assert seen==[ticker]

def test_unknown_calendar_stops_before_provider(fixed,tmp_path,monkeypatch):
    init_db();storage,name,keys,old=report();value,audit=observed();calls=[]
    before=storage.get_report(keys.data_key).content
    monkeypatch.setattr('data_freshness_market.market_calendar',lambda *a,**k:{'coverage_status':'unavailable','holidays':set()})
    with pytest.raises(HTTPException)as failure:
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    assert failure.value.status_code==409 and calls==[] and events()==[]
    assert storage.get_report(keys.data_key).content==before

def test_direct_service_requires_bound_context_before_provider(fixed):
    from data_fetch.types import FetchRequest
    value,audit=observed();calls=[]
    with pytest.raises(HTTPException):asyncio.run(service(value,audit,calls).fetch_source_async(FetchRequest.from_ticker('6214.TW'),'institutional_trading'))
    assert not calls

def test_actual_typed_provider_uses_existing_primary_and_official_recovery_once(fixed,tmp_path,monkeypatch):
    from data_fetch.taiwan_providers import InstitutionalTradingProvider
    from data_fetch import institutional_provider
    import official_institutional_source
    from data_fetch.market_sources import taiwan
    value,audit=observed();primary_calls=[];official_calls=[]
    def primary(ticker):primary_calls.append(ticker);return deepcopy(value)
    def official(ticker,primary,**kwargs):
        official_calls.append((ticker,kwargs));return primary,{}
    monkeypatch.setattr(taiwan,'fetch_institutional_trading_trend',primary)
    monkeypatch.setattr(official_institutional_source,'recover_institutional_observations',official)
    monkeypatch.setattr(institutional_provider,'call_provider_with_resilience',lambda provider,fn,args,kw:fn(*args,**kw))
    init_db();storage,name,keys,old=report()
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(registry=ProviderRegistry([InstitutionalTradingProvider()])),source='institutional_trading'))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert primary_calls==['6214.TW'] and len(official_calls)==1 and official_calls[0][1]['force_refresh']is False
    assert saved['data']['institutional_trading']['latest_session_admission']['eligible']is True
    assert saved['data']['institutional_trading']['observed_date_count']==30 and response['analysis_text_stale']is True

def test_fresh_phase_cache_keeps_original_epoch_and_does_not_reacquire_primary(fixed,tmp_path,monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.taiwan_providers import InstitutionalTradingProvider
    from data_fetch import institutional_provider
    import official_institutional_source
    from data_fetch.market_sources import taiwan
    cache_store.set_cache_backend(InMemoryCache())
    value,_=observed();calls=[]
    def primary(ticker):calls.append(ticker);return deepcopy(value)
    monkeypatch.setattr(taiwan,'fetch_institutional_trading_trend',primary)
    monkeypatch.setattr(official_institutional_source,'recover_institutional_observations',lambda ticker,primary,**kw:(primary,{}))
    monkeypatch.setattr(institutional_provider,'call_provider_with_resilience',lambda provider,fn,args,kw:fn(*args,**kw))
    init_db();storage,name,keys,old=report();svc=StockDataService(registry=ProviderRegistry([InstitutionalTradingProvider()]));saved=[]
    for _ in range(2):
        asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=svc,source='institutional_trading'))
        saved.append(json.loads(storage.get_report(keys.data_key).content))
    assert calls==['6214.TW']
    first=next(a for a in saved[0]['source_audit']if a['source']=='institutional_trading')
    second=next(a for a in saved[1]['source_audit']if a['source']=='institutional_trading')
    assert second['cache_hit']is True and second['fetched_at_epoch']==first['fetched_at_epoch']
    assert second['http_request_sent']is False and second['provider_attempts']==[]
    assert saved[1]['analysis_evidence']==old['analysis_evidence']
    cache_store.reset_cache_store_for_tests()


def _assert_snapshot_integrity(snapshot):
    from data_trust_snapshot_integrity import verify_data_snapshot_integrity, snapshot_size_bytes
    assert verify_data_snapshot_integrity(snapshot)['valid'] is True
    assert snapshot['content_hash']==snapshot['snapshot_hash']
    assert snapshot['reproducibility_packet']['data_snapshot_hash']==snapshot['snapshot_hash']
    assert snapshot['snapshot_size_bytes']==snapshot_size_bytes(snapshot)


def test_source_only_refresh_keeps_saved_analysis_contract_not_provider_decisions(fixed,tmp_path):
    init_db();storage,name,keys,old=report();value,audit=observed();calls=[]
    old['analysis_completeness']={'status':'quality_warning','quality_warning':True,'basis':'original analysis only'}
    old['oos_evaluation_inputs']={'pipeline_id':'v4','trade_setup':{'trade_direction':'Neutral','entry_zone':'N/A','core_catalyst':'original qualified statement'}}
    old['rerun_context']={'analyses':{'3':'original analysis'},'structured_outputs':{},'parsed':{'trade_setup':{'trade_direction':'Neutral'}},'pipeline_id':'v4','pipeline_label':None,'agent_sequence':None}
    old['conclusion_generated_at']=old['generated_at']
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=service(value,audit,calls),source='institutional_trading'))
    saved=json.loads(storage.get_report(keys.data_key).content)
    for key in ('analysis_completeness','oos_evaluation_inputs','rerun_context','conclusion_generated_at','analysis_evidence'):
        assert saved.get(key)==old[key], key
    assert saved['data']['institutional_trading']==value and len(calls)==1
    assert response['analysis_text_stale'] is True
    _assert_snapshot_integrity(saved)


def test_real_1301_before_snapshot_preserves_frozen_analysis_with_already_acquired_data(tmp_path):
    from report_persistence import report_bundle_keys_for_filename
    D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261014/remaining-gaps-after-cht'
    before_path=D/'institutional-recovery/1301.TW/before.data.json'
    after_path=D/'refresh-metadata-repair/author/actual-after.data.json'
    old=json.loads(before_path.read_text());new=json.loads(after_path.read_text())
    assert len(old['data']['institutional_trading']['daily_category_observations'])==84
    assert len(new['data']['institutional_trading']['daily_category_observations'])==90
    storage=InMemoryStorage();name='1301_TW_v4_report_job_e92a20881101.html';keys=report_bundle_keys_for_filename(name)
    storage.save_report(keys.data_key,before_path.read_bytes(),content_type='application/json')
    storage.save_report(keys.html_key,b'<html>immutable original analysis</html>',content_type='text/html')
    storage.save_report(keys.md_key,b'immutable original analysis',content_type='text/markdown')
    class NoProvider:
        async def fetch_async(self,*args,**kwargs):pytest.fail('provided data must not fetch')
    init_db();supplied=deepcopy(new['data']);input_copy=deepcopy(supplied)
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=NoProvider(),refreshed_data=supplied))
    saved=json.loads(storage.get_report(keys.data_key).content)
    for key in ('analysis_completeness','oos_evaluation_inputs','rerun_context','conclusion_generated_at','analysis_evidence',
                'report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
        assert saved.get(key)==old[key],key
    assert saved['data']==supplied==input_copy
    assert storage.get_report(keys.html_key).content==b'<html>immutable original analysis</html>'
    assert storage.get_report(keys.md_key).content==b'immutable original analysis'
    assert events()==[] and response['analysis_text_stale'] is True
    _assert_snapshot_integrity(saved)


def test_legacy_without_analysis_completeness_does_not_invent_success(fixed,tmp_path):
    init_db();storage,name,keys,old=report()
    assert 'analysis_completeness' not in old and 'oos_evaluation_inputs' not in old
    data=deepcopy(old['data']);data['parsed']={'trade_setup':{'trade_direction':'Long','entry_zone':'invented provider value'}}
    class NoProvider:
        async def fetch_async(self,*a,**k):pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=NoProvider(),refreshed_data=data))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert 'analysis_completeness' not in saved
    assert 'trade_setup' not in saved['oos_evaluation_inputs']
    _assert_snapshot_integrity(saved)


def test_saved_compact_oos_survives_trimmed_rerun_and_size_governance_keeps_omission_receipts(fixed,tmp_path,monkeypatch):
    import config
    monkeypatch.setattr(config,'DATA_SNAPSHOT_MAX_BYTES',50_000)
    init_db();storage,name,keys,old=report()
    old['analysis_completeness']={'status':'quality_warning','quality_warning':True}
    old['oos_evaluation_inputs']={'pipeline_id':'v4','trade_setup':{'trade_direction':'Neutral','core_catalyst':'saved compact contract; original parsed context was trimmed'}}
    old['rerun_context']={'analyses':{},'pipeline_id':'v4'}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    data=deepcopy(old['data']);data['recent_catalysts']=[{'title':f'item {i}','summary':'source text '*500}for i in range(20)]
    class NoProvider:
        async def fetch_async(self,*a,**k):pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=NoProvider(),refreshed_data=data))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert saved['oos_evaluation_inputs']==old['oos_evaluation_inputs']
    assert saved['analysis_completeness']==old['analysis_completeness']
    assert not saved['rerun_context'].get('parsed',{}).get('trade_setup')
    assert saved['snapshot_truncated'] is True
    assert 'data.recent_catalysts:17' in saved['snapshot_omitted_sections']
    assert len(saved['data']['recent_catalysts'])==3
    assert saved['snapshot_size_bytes']<=50_000
    _assert_snapshot_integrity(saved)


def test_explicit_unknown_saved_analysis_metadata_is_not_promoted(fixed,tmp_path):
    init_db();storage,name,keys,old=report()
    old['analysis_completeness']=None;old['oos_evaluation_inputs']={}
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    data=deepcopy(old['data']);data['parsed']={'trade_setup':{'trade_direction':'Long'}}
    class NoProvider:
        async def fetch_async(self,*a,**k):pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=NoProvider(),refreshed_data=data))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert saved['analysis_completeness'] is None and saved['oos_evaluation_inputs']=={}
    _assert_snapshot_integrity(saved)
