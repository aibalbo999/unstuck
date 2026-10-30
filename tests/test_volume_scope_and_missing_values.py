from datetime import date
import pandas as pd
import pytest
from market_screener_candidates import technical_candidates
from market_price_reconciliation import reconcile
from test_market_price_reconciliation import daily
from data_fetch.market_sources.twse_session_observation import parse_session


def frame(volumes,closes=None):
    return pd.DataFrame({'stock_id':['1301']*len(volumes),'date':pd.bdate_range(end='2026-10-02',periods=len(volumes)).strftime('%Y-%m-%d'),'close':closes or [100.]*len(volumes),'Trading_Volume':volumes})


@pytest.mark.parametrize('missing',[None,float('nan'),float('inf'),-1])
def test_missing_or_invalid_baseline_volume_cannot_manufacture_spike(missing):
    data=frame([missing]*19+[1000,1000])
    assert technical_candidates(data,scan_date=date(2026,10,2),top_n=10)==[]


def test_missing_volume_does_not_change_price_sma_and_bias_can_remain_research():
    data=frame([None]*20+[1000],[100.]*20+[130.])
    result=technical_candidates(data,scan_date=date(2026,10,2),top_n=10)[0]['metrics']
    assert result['ma20']==pytest.approx(101.5)
    assert result['volume_ratio'] is None and result['average_volume_20d'] is None


def test_missing_latest_volume_is_unknown_even_when_prices_show_bias():
    result=technical_candidates(frame([1000]*20+[None],[100.]*20+[130.]),scan_date=date(2026,10,2),top_n=10)[0]['metrics']
    assert result['latest_volume'] is None and result['volume_ratio'] is None


def test_complete_same_series_spike_uses_previous_twenty_samples():
    result=technical_candidates(frame([1000]*20+[3000]),scan_date=date(2026,10,2),top_n=10)[0]['metrics']
    assert result['volume_ratio']==3 and result['average_volume_20d']==1000
    assert 'previous 20' in result['volume_ratio_policy']


def test_equal_numbers_and_shares_do_not_verify_unknown_transaction_scope():
    result=reconcile(daily());assert result['volume']['value_match'] is True
    assert result['volume_scope_status']=='unverified_transaction_scope'
    assert result['cross_provider_volume_comparable'] is False
    assert result['cross_provider_flow_normalization_allowed'] is False


def test_only_explicit_identical_verified_scope_can_be_comparable():
    data=daily()
    for key in ['provider_raw_observation','official_observation']:
        data[key].update(volume_scope='same_venue_scope',volume_scope_verified=True)
    assert reconcile(data)['cross_provider_volume_comparable'] is True
    data['official_observation']['volume_scope']='other_scope'
    assert reconcile(data)['cross_provider_volume_comparable'] is False


def test_official_scope_is_bound_to_returned_table_note_not_invented():
    from test_market_price_reconciliation import official_payload
    p=official_payload();note='本統計資訊含一般、零股、盤後定價、鉅額交易，不含拍賣、標購。';p['tables'][0]['notes']=[note]
    row=parse_session(p,'2026-10-02')['1301'];assert row['volume_scope_verified'] is True and row['volume_scope_note']==note
    p['tables'][0].pop('notes');assert parse_session(p,'2026-10-02')['1301']['volume_scope_verified'] is False
