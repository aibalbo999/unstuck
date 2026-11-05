from copy import deepcopy
from datetime import date
from hashlib import sha256
import json,time
import pytest
from test_starair_reference_income import income
from test_peer_reference_income import index_body,reference_body
from test_peer_reference_transport import parts
from data_fetch.market_sources import peer_reference_transport as t

DAY=date(2026,11,3)


@pytest.fixture
def individual_environment(monkeypatch):
    from data_fetch.market_sources import starair_reference_evidence as e
    import cache_store
    store={};calls=[]
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store,'peek_cache_json',lambda key:deepcopy(store.get(key)))
    monkeypatch.setattr(e,'peek_cache_json',lambda key:deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store,'set_cache_json',lambda key,value,ttl_seconds=None:store.__setitem__(key,deepcopy(value)))
    rows=[{'公司代號':str(1000+i)}for i in range(800)]+[{'公司代號':'2646','公司名稱':'星宇航空股份有限公司','公司簡稱':'星宇航空','營利事業統一編號':'51712072','出表日期':'1151103','產業別':'15','編制財務報表類型':'2','特別股':'0','已發行普通股數或TDR原股發行股數':'3426710000'}]
    raw=json.dumps(rows,ensure_ascii=False).encode()
    master={'cache_hit':True,'stale':False,'fetched_at_epoch':time.time()-10,'cache_source':'official-company-roster:v2:.TW','source_url':'https://openapi.twse.com.tw/v1/opendata/t187ap03_L','source_payload_sha256':sha256(raw).hexdigest(),'source_payload_bytes':len(raw),'evidence_kind':'cached_complete_source_payload_verified_by_digest','http_status_observed':False}
    monkeypatch.setattr(e,'read_cached_listed_roster_bytes',lambda:(raw,deepcopy(master)))
    def download(self,request,diag):
        calls.append(deepcopy(request));p=request['params'];kind=request['kind']
        if kind=='home':body='<html><body><a name="IncomeStatement">綜合損益表(累計)</a></body></html>'.encode()
        elif kind=='methodology':body=('<html><head><meta charset="utf-8"></head><body><li>本益比=收盤價／每股參考稅後純益；每股參考稅後純益=該公司稅後參考純益／發行參考股數；當每股參考稅後純益為0或負數時，則不計算本益比。近滿4季財務報告為計算基礎</li></body></html>').encode()
        elif kind=='reference':body=reference_body().decode().replace('20261104','20261103').replace('6230','2646').replace('尼得科超眾','星宇航空').encode()
        elif kind=='index':body=index_body(p['year'],[2]if p['year']==2026 else[2,4]).decode('big5').replace('6230','2646').replace('尼得科超眾','星宇航空').replace('IFRSs合併財報','IFRSs個別財報').replace('_AI1.pdf','_AI2.pdf').encode('big5')
        else:body=income(p['year'],p['quarter'],value=str({(2026,2):-345520,(2025,2):923243,(2025,4):272608}[(p['year'],p['quarter'])]))
        return self._consume(request,request['url'],parts(request,body=body),0,None,diag)
    monkeypatch.setattr(t.PeerIncomeHttp,'_download',download)
    from provider_correlation import correlation_scope, source_operation
    from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
    import provider_sla
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda entries: None)
    with correlation_scope(replace=True,ticker='6757.TW',fetch_id='isolated-simulation'), source_operation('dynamic_peer_metrics','FinMind/yfinance'), receipt_observation_scope(True):
        yield e,store,calls,master


def test_individual_producer_replays_full_originals_and_keeps_numeric_PE_empty(individual_environment):
    e,store,calls,master=individual_environment
    v=e.collect_reference_income('2646.TW','2026-11-03',today=DAY)
    proof=v['source_record_archive']
    d=e.verified_reference_income(proof,ticker='2646.TW',observed_at='2026-11-03',today=DAY)
    assert d['net_income_twd']==-996155000 and d['basis']=='reported_cumulative_individual_income'
    assert v['scope']=='individual_issuer_income'and proof['schema']=='twse-individual-reference-income.v1'
    assert 'pe_ttm'not in v and len(calls)==8
    assert all(c['params']['individual_reference_issuer']=='2646.TW'for c in calls if c['kind']in{'income','index'})


@pytest.mark.parametrize('damage',['amount','period','issuer','schema','component','request','owner','master','observed_day'])
def test_unbound_public_flags_cannot_replace_individual_originals(individual_environment,damage):
    e,store,calls,master=individual_environment
    proof=deepcopy(e.collect_reference_income('2646.TW','2026-11-03',today=DAY)['source_record_archive'])
    if damage=='amount':proof['derived']['net_income_twd']+=1
    elif damage=='period':proof['derived']['period_start']='2026-01-01'
    elif damage=='issuer':proof['ticker']='6230.TW'
    elif damage=='schema':proof['schema']='twse-peer-reference-income.v1'
    elif damage=='component':proof['components'].pop('income:2025Q2')
    elif damage=='request':proof['components']['income:2026Q2']['spec']['data']['companyId']='6230 尼得科超眾'
    elif damage=='owner':store.clear()
    elif damage=='master':master['source_payload_sha256']='0'*64
    else:proof['observed_at']='2026-11-04'
    assert e.verified_reference_income(proof,ticker='2646.TW',observed_at='2026-11-03',today=DAY)is None


def test_existing_annual_guard_prevents_new_namespace_refresh(individual_environment):
    e,store,calls,master=individual_environment
    store['financial_data:2646.TW']={'source_audit':[{'source':'financial_statements','status':'success','documents':[{'filename':'existing annual'}]}]}
    with pytest.raises(ValueError):e.collect_reference_income('2646.TW','2026-11-03',today=DAY)
    assert calls==[]


def test_other_issuer_and_future_observation_are_not_licensed(individual_environment):
    e,store,calls,master=individual_environment
    for symbol,day in [('6230.TW','2026-11-03'),('6558.TW','2026-11-03'),('2646.TW','2026-11-04')]:
        with pytest.raises(ValueError):e.collect_reference_income(symbol,day,today=DAY)
    assert calls==[]


def test_research_scope_or_unbound_frame_does_not_write_new_individual_owners(individual_environment):
    e,store,calls,master=individual_environment
    from provider_correlation import correlation_scope
    from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
    before=deepcopy(store)
    with receipt_observation_scope(False):
        with pytest.raises(ValueError):e.collect_reference_income('2646.TW','2026-11-03',today=DAY)
    with correlation_scope(replace=True):
        with pytest.raises(ValueError):e.collect_reference_income('2646.TW','2026-11-03',today=DAY)
    assert calls==[]and store==before
