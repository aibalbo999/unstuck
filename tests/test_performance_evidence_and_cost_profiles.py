from datetime import date
import pytest
from performance_evidence_quarantine import project_results,DISPUTED_FILENAME
from cost_profile_sensitivity import evaluate_profiles


def saved(**kwargs):
    row={'ticker':'2382.TW','report_filename':DISPUTED_FILENAME,'horizon_trading_days':10,'generated_date':'2026-09-05','status':'horizon_exit','entry_date':'2026-09-07','exit_date':'2026-09-18','entry_price':345,'exit_price':344,'strategy_roi_pct':-.2899,'outcome':'miss','trade_direction':'Long'}
    row.update(kwargs);return row


def test_quarantine_preserves_original_and_is_idempotent():
    original=saved(); projection=project_results([original])[0]
    assert original['strategy_roi_pct']==-.2899 and original['status']=='horizon_exit'
    assert projection['strategy_roi_pct'] is None and projection['recorded_strategy_roi_pct']==-.2899
    assert project_results([projection])==[projection]


def test_invalid_session_is_quarantined_without_replacement():
    row=saved(report_filename='other.html',exit_date='2026-09-20')
    assert 'exit_date_outside_verified_sessions' in project_results([row])[0]['quarantine_reasons']


def policy():
    return {'as_of':'2026-10-02','tax_rule_source':'official','instrument_classes':{'2382.TW':'equity_assumption','0050.TW':'equity_etf_0050_verified'},'profiles':[{'id':'test','commission_percent_each_side':.1,'round_trip_slippage_bps':20,'short_borrow_financing_bps_per_calendar_day':2}]}


def test_cost_tax_side_and_short_borrow():
    row=saved(report_filename='other',entry_price=100,exit_price=110,strategy_roi_pct=10)
    slot={'ticker':'2382.TW','state':'horizon_exit','stored_result':row}
    cost=evaluate_profiles([slot],policy())['rows'][0]['profiles']['test']
    assert cost['commission_cost_pct']==.21 and cost['conditional_tax_cost_pct']==.33
    assert cost['hypothetical_net_roi_pct']==9.26
    row.update(trade_direction='Short',exit_price=90,strategy_roi_pct=10)
    cost=evaluate_profiles([slot],policy())['rows'][0]['profiles']['test']
    assert cost['conditional_tax_cost_pct']==.3 and cost['borrow_financing_cost_pct']==.22
    assert cost['hypothetical_net_roi_pct']==9.09


def test_etf_rate_and_quarantine_subset():
    row=saved(ticker='0050.TW',report_filename='etf',entry_price=100,exit_price=110,strategy_roi_pct=10)
    slots=[{'ticker':'0050.TW','state':'horizon_exit','stored_result':row},{'ticker':'2382.TW','state':'horizon_exit','stored_result':saved()}]
    result=evaluate_profiles(slots,policy())
    assert result['rows'][0]['tax_rate_pct']==.1
    assert result['summaries']['all_saved_illustration']['test']['count']==2
    assert result['summaries']['not_quarantined_conditional']['test']['count']==1
    assert result['validated_net_results']==0


@pytest.mark.parametrize('bad',[True,-1,float('nan'),float('inf')])
def test_invalid_cost_rejected(bad):
    p=policy();p['profiles'][0]['round_trip_slippage_bps']=bad
    with pytest.raises(ValueError):evaluate_profiles([],p)


def test_unknown_class_not_default_equity():
    p=policy();p['instrument_classes']={}
    result=evaluate_profiles([{'ticker':'2382.TW','state':'horizon_exit','stored_result':saved()}],p)
    assert result['mature_gross_count']==0
