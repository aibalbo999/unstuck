import copy
import pytest
import maturity_source_admission as m
from report_source_admission import price_admission

def test_two_official_missing_and_wrong_maturity_fail_closed():
    assert m.assess_maturity_source([{'date':'2026-10-07'}],'3324.TWO','2026-10-07')['reason']=='latest_official_price_raw_evidence_missing'
    assert m.assess_maturity_source([{'date':'2026-10-06'}],'3324.TWO','2026-10-07')['reason']=='maturity_session_bar_missing'

@pytest.mark.parametrize('ticker',['3324.TWO','2371.TW'])
def test_price_mismatch_stays_ineligible_for_both_markets(monkeypatch,ticker):
    monkeypatch.setattr(m,'price_admission',lambda *a:{'eligible':True,'raw_evidence':{'status':'archived'}})
    proof={'open':100,'high':101,'low':99,'close':100};bar={'date':'2026-10-07',**proof,'observation_provenance':{'official_observation':copy.deepcopy(proof)}};bar['close']=100.5
    r=m.assess_maturity_source([bar],ticker,'2026-10-07')
    assert not r['eligible'] and r['reason']=='maturity_provider_official_price_mismatch'
    assert r['finality_guaranteed'] is False

def test_twse_raw_endpoint_cannot_be_used_as_tpex(monkeypatch):
    from data_fetch.market_sources.twse_session_observation import DATED_URL
    import market_evidence_policy
    monkeypatch.setattr(market_evidence_policy,'acquisition_phase',lambda *a:'post_cutoff')
    proof={'status':'archived','evidence_kind':'raw_http_response_bytes','retrieved_at':'2026-10-07T14:00:00+00:00','source_url':DATED_URL+'?date=20261007&type=ALL&response=json','http_status':200}
    r=price_admission({'as_of':'2026-10-07','official_observation':{'ticker':'3324.TWO','date':'2026-10-07','raw_evidence':proof}},'3324.TWO')
    assert not r['eligible'] and r['reason']=='official_price_market_source_mismatch'

def test_two_source_wait_retry_never_records_attempt(monkeypatch,tmp_path):
    from datetime import date
    from types import SimpleNamespace
    import sqlite3
    import legacy_evidence_revisions as r
    import mode_trade_backtest,report_history_storage,report_artifacts
    original={'report_filename':'3324_TWO_test.html','horizon_trading_days':10}
    scope={'scope_id':'a'*64,'ticker':'3324.TWO','report_filename':original['report_filename'],'generated_date':'2026-09-21','maturity_date':'2026-10-07','sessions':['2026-10-07'],'original_payload_sha256':r.digest(original)}
    path=tmp_path/'isolated.sqlite3'
    with sqlite3.connect(path) as c:c.execute('CREATE TABLE trade_evidence_revisions_v1(batch_id,scope_id,as_of_session,state)')
    monkeypatch.setattr(r,'_connect',lambda:sqlite3.connect(path))
    monkeypatch.setattr(r,'active_manifests',lambda:[{'batch_id':'test','rows':[scope]}])
    monkeypatch.setattr(r,'session_window',lambda *a:{'status':'verified','sessions':scope['sessions']})
    monkeypatch.setattr(r.trade_backtest_store,'list_results',lambda **kw:[original])
    def exact_result(*, report_filename, horizon_trading_days):
        assert report_filename == original['report_filename'] and horizon_trading_days == 10
        return original
    monkeypatch.setattr(r.trade_backtest_store, 'get_result', exact_result)
    monkeypatch.setattr(r,'append_revision',lambda *a:pytest.fail('source wait cannot append or record attempt'))
    monkeypatch.setattr(mode_trade_backtest,'_parsed_snapshot',lambda *a:{})
    monkeypatch.setattr(mode_trade_backtest,'_plan_inputs',lambda *a:({},[10],''))
    monkeypatch.setattr(report_artifacts.ReportArtifactLocator,'require_key',lambda *a,**kw:'isolated')
    monkeypatch.setattr(report_history_storage,'storage_for_existing_output_dir',lambda *a:SimpleNamespace(get_report=lambda k:SimpleNamespace(content=b'{"data": {}}')))
    for _ in range(2):
        result=r.run_due_revisions(output_dir='isolated',as_of=date(2026,10,7),bar_fetcher=lambda *a:[{'date':'2026-10-07','open':1,'high':2,'low':1,'close':1}])
        assert result['awaiting_source_evidence']==1 and result['already_attempted_session']==0 and result['new_revisions']==0
        assert result['source_waits'][0]['ticker']=='3324.TWO'
        assert result['source_waits'][0]['source_gate']['reason']=='latest_official_price_raw_evidence_missing'
    with sqlite3.connect(path) as c:assert c.execute('select count(*) from trade_evidence_revisions_v1').fetchone()[0]==0

def test_two_official_observation_date_mismatch_fails_before_raw_parser():
    official={'ticker':'3324.TWO','date':'2026-10-06','raw_evidence':{'status':'archived','evidence_kind':'raw_http_response_bytes'}}
    r=price_admission({'as_of':'2026-10-07','official_observation':official},'3324.TWO')
    assert not r['eligible'] and r['reason']=='latest_official_price_raw_evidence_missing'
    assert r['historical_point_in_time_verified'] is False and r['finality_guaranteed'] is False
