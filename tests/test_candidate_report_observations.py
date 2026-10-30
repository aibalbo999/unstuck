import json
from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import pytest
from candidate_report_observations import load_candidate_report_observations

MOMENT=datetime(2026,10,2,10,tzinfo=ZoneInfo('Asia/Taipei'))


def snapshot():
    return {'data':{'ticker':'2330.TW','daily_market_data':{'as_of':'2026-10-01','source':'fixture',
        'bars':[{'date':'2026-10-01','close':100,'volume':10}]},
        'institutional_trading':{'observation_dates':['2026-09-30'],'source':'fixture'}},'generated_at':'2026-10-01T15:00:00+08:00'}


def fixture_file(tmp_path,value):
    # Standard companion paths, actual locator used rather than mocked filename loading.
    filename='2330_TW_v4_report_job_fixture.html'
    (tmp_path/'2330_TW_v4_report_job_fixture.data.json').write_text(json.dumps(value))
    return filename


def test_real_locator_reads_data_without_html_and_does_not_relabel_screener(tmp_path):
    filename=fixture_file(tmp_path,snapshot())
    items=[{'ticker':'2330.TW','screen_date':'2026-09-30','metrics':{'close':90},'latest_report':{'filename':filename}}]
    before=deepcopy(items)
    result=load_candidate_report_observations([{'ticker':'2330.TW'}],items,str(tmp_path),moment=MOMENT)['2330.TW']
    assert result['status']=='available' and result['price_observation_date']=='2026-10-01'
    assert result['institutional_observation_date']=='2026-09-30'
    assert result['latest_source_dates_aligned'] is False and result['actionable'] is False
    assert len(result['snapshot_sha256'])==64 and result['historical_available_at_verified'] is False
    assert items==before and len(list(tmp_path.iterdir()))==1


@pytest.mark.parametrize('error',['wrong_ticker','bar_mismatch','future','invalid_date','corrupt','absent'])
def test_missing_corrupt_or_mismatched_evidence_fails_closed_and_recovers(tmp_path,error):
    value=snapshot()
    if error=='wrong_ticker':value['data']['ticker']='2317.TW'
    if error=='bar_mismatch':value['data']['daily_market_data']['bars'][0]['date']='2026-09-30'
    if error=='future':value['data']['institutional_trading']['observation_dates']=['2026-10-05']
    if error=='invalid_date':value['data']['daily_market_data']['as_of']='not-a-date'
    filename=fixture_file(tmp_path,value);path=next(tmp_path.iterdir())
    if error=='corrupt':path.write_text('not json')
    if error=='absent':path.unlink()
    items=[{'ticker':'2330.TW','latest_report':{'filename':filename}}]
    r=load_candidate_report_observations([{'ticker':'2330.TW'}],items,str(tmp_path),moment=MOMENT)['2330.TW']
    assert r['status']=='unavailable' and r['actionable'] is False
    fixture_file(tmp_path,snapshot())
    assert load_candidate_report_observations([{'ticker':'2330.TW'}],items,str(tmp_path),moment=MOMENT)['2330.TW']['status']=='available'


def test_source_observation_dates_persist_even_when_other_source_missing():
    import pandas as pd
    from market_screener_candidates import build_screener_candidates
    inst=pd.DataFrame([{'date':'2026-10-01','stock_id':'2330','name':'Foreign_Investor','buy':200,'sell':0},
                       {'date':'2026-10-01','stock_id':'2330','name':'Investment_Trust','buy':100,'sell':0}])
    rows=build_screener_candidates(inst,pd.DataFrame(),scan_date=date(2026,10,1),top_n=10)
    assert rows[0]['metrics']['flow_observation_date']=='2026-10-01'
    assert rows[0]['metrics']['normalized_flow_pct'] is None


def test_future_same_date_inputs_recalculate_ratio_but_not_mismatched_dates():
    import pandas as pd
    from market_screener_candidates import build_screener_candidates
    inst=pd.DataFrame([{'date':'2026-10-01','stock_id':'2330','name':'Foreign_Investor','buy':200,'sell':0},
                       {'date':'2026-10-01','stock_id':'2330','name':'Investment_Trust','buy':100,'sell':0}])
    daily=pd.DataFrame([{'date':'2026-10-01','stock_id':'2330','close':100,'Trading_Volume':1000,'monthly_average_close':90}])
    row=build_screener_candidates(inst,daily,scan_date=date(2026,10,1),top_n=10)[0]
    assert row['metrics']['normalized_flow_pct']==30
    assert row['metrics']['price_observation_date']==row['metrics']['flow_observation_date']=='2026-10-01'
    assert row['metrics']['average_volume_20d'] is None and row['metrics']['volume_ratio'] is None
    daily['date']='2026-09-30'
    row=build_screener_candidates(inst,daily,scan_date=date(2026,10,1),top_n=10)[0]
    assert row['metrics']['normalized_flow_pct'] is None
    assert row['metrics']['price_observation_date']=='2026-09-30' and row['metrics']['flow_observation_date']=='2026-10-01'


def test_offline_capture_hash_failure_cannot_be_bypassed_by_provider_fetch(tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'scripts/replay_screener_observations.py'
    spec=importlib.util.spec_from_file_location('captured_replay',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'foreign.json').write_text('{}')
    (tmp_path/'manifest.json').write_text(json.dumps({'foreign':{'raw_sha256':'0'*64}}))
    with pytest.raises(ValueError,match='capture hash mismatch'):
        module.replay(tmp_path,date(2026,10,1))
