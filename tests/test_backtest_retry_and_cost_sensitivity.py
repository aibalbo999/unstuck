from copy import deepcopy
from datetime import date
import pytest
from backtest_session_contract import session_window
from cost_sensitivity import cost_sensitivity


@pytest.fixture
def mode(monkeypatch):
    import mode_trade_backtest as module
    from test_hcs_research_contracts import context
    monkeypatch.setattr(module,'_parsed_snapshot',lambda *a:{'trade_setup':{'trade_direction':'Long','entry_zone':100,'target_price':110,'stop_loss':90}})
    monkeypatch.setattr(module,'_execution_context',lambda *a:context())
    monkeypatch.setattr(module.trade_backtest_store,'list_results',lambda **kw:[])
    saved=[];monkeypatch.setattr(module.trade_backtest_store,'save_result',lambda row:saved.append(row))
    return module,saved


def call(module,day,fetch):
    return module.evaluate_report_trades(report={'filename':'new','ticker':'2330.TW'},pipeline_id='v4',generated=date(2026,10,2),as_of=day,output_dir='unused',bar_fetcher=fetch)


def test_immature_new_window_neither_fetches_nor_saves_failure(mode):
    module,saved=mode
    rows,skips=call(module,date(2026,10,6),lambda *a:pytest.fail('No premature provider request'))
    assert not rows and not saved and len(skips)==2
    assert all(s['reason']=='awaiting_verified_maturity' for s in skips)


def test_mature_empty_provider_is_retryable_and_recovers_next_poll(mode):
    module,saved=mode;window=session_window(date(2026,10,2),10);due=date.fromisoformat(window['maturity_date'])
    rows,skips=call(module,due,lambda *a:[])
    assert not rows and not saved and all(s.get('retryable') is True for s in skips)
    bars=[{'date':d,'open':100,'high':102,'low':99,'close':101,'stock_splits':0,'dividends':0} for d in window['sessions']]
    rows,skips=call(module,due,lambda *a:bars)
    assert len(rows)==2 and len(saved)==2


def test_mature_missing_session_is_not_saved_terminal(mode):
    module,saved=mode;window=session_window(date(2026,10,2),10)
    bars=[{'date':d,'open':100,'high':102,'low':99,'close':101,'stock_splits':0,'dividends':0} for d in window['sessions']];del bars[1]
    rows,skips=call(module,date.fromisoformat(window['maturity_date']),lambda *a:bars)
    assert not rows and not saved and all(s['reason']=='session_coverage_incomplete' for s in skips)


def test_cost_scenarios_do_not_include_immature_or_claim_actual_net_result():
    slots=[{'ticker':'2330.TW','state':'horizon_exit','stored_result':{'strategy_roi_pct':.2}},
           {'ticker':'2317.TW','state':'not_matured','stored_result':{'strategy_roi_pct':10}},
           {'ticker':'2303.TW','state':'no_trade','stored_result':{'strategy_roi_pct':0}}]
    before=deepcopy(slots);r=cost_sensitivity(slots,[10,50])
    assert r['mature_executed_gross_count']==1 and slots==before
    assert r['rows'][0]['hypothetical_net_roi_pct']=={'10.0':.1,'50.0':-.3}
    assert r['validated_net_results']==0 and r['actual_cost_verified'] is False
    assert r['excluded_state_counts']=={'not_matured':1,'no_trade':1}


@pytest.mark.parametrize('costs',[[],[None],[True],[-1],[float('nan')],[float('inf')]])
def test_cost_unknown_never_defaults_to_zero(costs):
    with pytest.raises(ValueError):cost_sensitivity([],costs)


def test_refresh_failure_does_not_suppress_backtest_poll_and_poll_is_observable(monkeypatch):
    import asyncio
    import decision_tracking_scheduler as scheduler
    calls,logs=[],[]
    async def fail_refresh(**kw):
        calls.append('refresh');raise RuntimeError('fixture refresh failure')
    def poll(**kw):
        calls.append('backtest');return {'evaluated_count':0,'skipped':[{'retryable':True}],'errors':[]}
    async def stop(interval):
        assert interval==900
        raise asyncio.CancelledError
    monkeypatch.setattr(scheduler.decision_tracking_service,'refresh_tracking_items',fail_refresh)
    monkeypatch.setattr(scheduler.decision_tracking_service,'run_due_backtests',poll)
    monkeypatch.setattr(scheduler.asyncio,'sleep',stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_decision_tracking_scheduler(get_output_dir=lambda:'unused',get_refresh_service=lambda:object(),emit_log=logs.append))
    assert calls==['refresh','backtest']
    assert any('回測輪詢完成' in log and 'retryable_data_gaps=1' in log for log in logs)
