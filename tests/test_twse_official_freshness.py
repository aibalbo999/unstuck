"""A supported TWSE source needs its own original timestamp, not package time."""
from copy import deepcopy
import pytest
import data_freshness


@pytest.mark.parametrize('entry',[None,{}, {'cache_generated_at_epoch':999.}, {'market_data_fetched_at_epoch':999.}])
def test_twse_never_borrows_package_or_market_time(monkeypatch,entry):
    monkeypatch.setattr(data_freshness.time_module,'time',lambda:1000.)
    data={'ticker':'2330.TW','twse_official':{'revenue_ttm_raw':100},
          'cache_generated_at_epoch':999.,'market_data_fetched_at_epoch':998.}
    if entry is not None:data['source_freshness']={'twse_official':entry}
    before=deepcopy(data)
    assert data_freshness.source_timestamp_epoch(data,'twse_official')is None
    entry=data_freshness.build_source_freshness(data,'2330.TW',True,now_epoch=1000.)['twse_official']
    assert entry['fetched_at_epoch']is None and entry['is_fresh']is False and entry['stale']is True
    assert data==before


@pytest.mark.parametrize('entry',[
    {'fetched_at_epoch':True}, {'fetched_at_epoch':False}, {'fetched_at_epoch':float('nan')},
    {'fetched_at_epoch':float('inf')}, {'fetched_at_epoch':10**500}, {'fetched_at_epoch':-1},
    {'fetched_at_epoch':1001.}, {'fetched_at_epoch':'900'}, {'fetched_at':'1970-01-01T00:15:00'},
    {'fetched_at':'garbled'}, {'fetched_at':'1970-01-01T00:16:41+00:00'},
    {'fetched_at_epoch':900.,'fetched_at':'1970-01-01T00:14:00+00:00'},
    {'fetched_at_epoch':900.,'fetched_at':False},
    {'fetched_at_epoch':1000.,'fetched_at':'1970-01-01T00:16:40.500000+00:00'},
    {}, None,
])
def test_invalid_explicit_twse_evidence_cannot_fall_through_to_later_stamp(monkeypatch,entry):
    monkeypatch.setattr(data_freshness.time_module,'time',lambda:1000.)
    data={'source_freshness':{'twse_official':entry},'twse_official_fetched_at_epoch':999.,
          'cache_generated_at_epoch':999.,'source_audit':[{'source':'twse_official','fetched_at_epoch':999.}]}
    assert data_freshness.source_timestamp_epoch(data,'twse_official')is None


@pytest.mark.parametrize('entry',[
    {'fetched_at_epoch':900.}, {'fetched_at':'1970-01-01T00:15:00+00:00'},
    {'fetched_at':'1970-01-01T08:15:00+08:00'},
    {'fetched_at_epoch':900.,'fetched_at':'1970-01-01T00:15:00Z'},
])
def test_original_twse_epoch_or_aware_iso_survives_both_source_locations(monkeypatch,entry):
    monkeypatch.setattr(data_freshness.time_module,'time',lambda:1000.)
    for data in ({'source_freshness':{'twse_official':entry}},
                 {'source_freshness':{'market_data':{'fetched_at_epoch':999.}},
                  **{'twse_official_'+key:value for key,value in entry.items()}}):
        data.update(ticker='2330.TW',cache_generated_at_epoch=999.)
        assert data_freshness.source_timestamp_epoch(data,'twse_official')==900.
        fresh=data_freshness.build_source_freshness(data,'2330.TW',True,now_epoch=1000.)['twse_official']
        assert fresh['fetched_at_epoch']==900. and fresh['is_fresh']is True


def test_unselected_audit_is_not_promoted_and_other_source_policy_is_unchanged(monkeypatch):
    monkeypatch.setattr(data_freshness.time_module,'time',lambda:1000.)
    data={'cache_generated_at_epoch':999.,'source_audit':[{'source':'twse_official','fetched_at_epoch':999.,'status':'error'}]}
    assert data_freshness.source_timestamp_epoch(data,'twse_official')is None
    assert data_freshness.source_timestamp_epoch(data,'monthly_revenue')==999.
    data['source_freshness']={'market_data':{'fetched_at_epoch':998.}}
    assert data_freshness.source_timestamp_epoch(data,'twse_official')is None


@pytest.mark.parametrize('ticker,kind',[('AAPL','EQUITY'),('0050.TW','ETF')])
def test_twse_canonical_projection_keeps_existing_market_and_instrument_applicability(ticker,kind):
    data={'ticker':ticker,'instrument_type':kind,'source_freshness':{'twse_official':{'fetched_at_epoch':900.}}}
    entry=data_freshness.build_source_freshness(data,ticker,True,now_epoch=1000.)['twse_official']
    assert entry['status']=='not_applicable' and entry['is_fresh']is None and entry['stale']is False


def test_captured_allis_original_projection_retains_twse_and_earlier_core_stamps(monkeypatch):
    import json
    import time
    from pathlib import Path
    from hashlib import sha256
    from report_source_refresh import _reassess_original_freshness
    path=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261014/allis-conference-integration/root/before.data'
    raw=path.read_bytes()
    assert sha256(raw).hexdigest()=='1267a68442fd18739280e2f8d3b4a411c23bc8f4f1616283e05424696af4bd64'
    before=json.loads(raw)['data'];data=deepcopy(before);now=1791951972.089216
    monkeypatch.setattr(time,'time',lambda:now)
    audit={'source':'earnings_call','status':'success','fetched_at_epoch':now,'cache_hit':False}
    data['source_audit']=[a for a in data['source_audit']if a['source']!='earnings_call']+[audit]
    original_audits=deepcopy(data['source_audit'])
    _reassess_original_freshness(data,'1514.TW','earnings_call',[audit])
    twse=data['source_freshness']['twse_official']
    assert twse['fetched_at_epoch']==before['source_freshness']['twse_official']['fetched_at_epoch']
    assert twse['stale']is True and twse['is_fresh']is False
    assert data['source_freshness']['market_data']['fetched_at_epoch']==1791358399.65227
    assert data['source_freshness']['financial_statements']['fetched_at_epoch']==1791358490.59807
    assert data['source_audit']==original_audits
    derived={'source_freshness','data_freshness','data_trust','source_audit'}
    assert {k:v for k,v in data.items()if k not in derived}=={k:v for k,v in before.items()if k not in derived}
