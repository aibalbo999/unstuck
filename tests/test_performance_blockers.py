from copy import deepcopy
from datetime import date
import pytest
from performance_blockers import blocker_summary, net_eligible
from test_hcs_research_contracts import bars, context, evaluate
from backtest_price_comparability import assess_price_comparability


@pytest.mark.parametrize('field', ['session_contract', 'price_comparability', 'cost_evidence'])
@pytest.mark.parametrize('invalid', [None, [], 'unknown', 1])
def test_invalid_legacy_contract_metadata_is_unverified(field, invalid):
    old = {'session_contract': {'status': 'verified'}, 'price_comparability': {'status': 'verified'},
           'cost_evidence': {'status': 'complete_declared_assumptions'}, 'net_outcome': 'hit'}
    old[field] = invalid
    rows = [{'state': 'target_first', 'stored_result': old}]
    before = deepcopy(rows)
    assert not net_eligible(rows[0])
    result = blocker_summary(rows)
    assert result['partition'] == {'executed_result_unverified': 1}
    assert result['executed_contract_blockers'][field + ':metadata_not_saved'] == 1
    assert rows == before


def test_partition_distinguishes_missing_metadata_from_waiting_and_recorded_failure():
    rows = [{"state":"not_matured", "stored_result":{"status":"insufficient_data","reason":"missing_ohlc"}},
            {"state":"target_first","stored_result":{"outcome":"hit"}},
            {"state":"insufficient_data","stored_result":{"reason":"unsupported_conditional_entry"}},
            {"state":"matured_missing_result"},{"state":"no_trade"}]
    before=deepcopy(rows); result=blocker_summary(rows)
    assert sum(result['partition'].values())==5 and rows==before
    assert result['partition']['awaiting_maturity']==1
    assert result['stored_failure_reasons']=={'unsupported_conditional_entry':1}
    assert result['executed_contract_blockers']['price_comparability:metadata_not_saved']==1


def test_premature_saved_verified_result_cannot_be_counted_as_eligible():
    old={'session_contract':{'status':'verified'},'price_comparability':{'status':'verified'},
         'cost_evidence':{'status':'complete_declared_assumptions'},'net_outcome':'hit'}
    assert not net_eligible({'state':'not_matured','stored_result':old})
    assert net_eligible({'state':'target_first','stored_result':old})


@pytest.mark.parametrize('value',[None,float('nan'),float('inf'),-1,True])
def test_unknown_action_values_are_not_no_events(value):
    rows=bars();rows[0]['dividends']=value
    assert assess_price_comparability(context(),rows)['reason']=='corporate_actions_coverage_unknown'


def test_provider_flags_do_not_prove_raw_exchange_prices_and_fingerprint_is_retained():
    rows=bars()
    for row in rows:
        row['observation_provenance']={'provider':'fixture','price_basis':'provider_ohlc_auto_adjust_false',
            'retrieved_at':'2026-01-20T00:00:00+00:00','auto_adjust':False}
    result=evaluate(rows)
    assert result['reason']=='provider_raw_basis_not_established'
    assert result['bar_observation']['provenance']['auto_adjust'] is False
    assert len(result['bar_observation']['sha256'])==64
    assert result['net_outcome'] is None
    changed=deepcopy(rows);changed[0]['close']+=1
    assert evaluate(changed)['bar_observation']['sha256']!=result['bar_observation']['sha256']


def test_future_fetch_records_query_and_acquisition_not_backdated_availability():
    import pandas as pd
    from market_price_history import fetch_backtest_bars
    class Provider:
        def history(self,**kwargs):
            assert kwargs['auto_adjust'] is False and kwargs['actions'] is True
            return pd.DataFrame({'Open':[100],'High':[101],'Low':[99],'Close':[100],
                                 'Stock Splits':[0],'Dividends':[0]},index=pd.to_datetime(['2026-01-02']))
    row=fetch_backtest_bars('2330.TW',date(2026,1,1),date(2026,1,5),ticker_factory=lambda _:Provider())[0]
    evidence=row['observation_provenance']
    assert evidence['query_end_exclusive']=='2026-01-06'
    assert evidence['price_basis']=='provider_ohlc_auto_adjust_false'
    assert 'available_at' not in evidence and evidence['retrieved_at']
