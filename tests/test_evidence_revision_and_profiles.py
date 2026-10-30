from datetime import date
import pytest
import legacy_evidence_revisions as revisions
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


def test_not_mature_does_not_fetch(monkeypatch):
    scope={'scope_id':'one','maturity_date':'2026-10-02'}
    monkeypatch.setattr(revisions,'active_manifests',lambda:[{'rows':[scope]}])
    monkeypatch.setattr(revisions.trade_backtest_store,'list_results',lambda **kw:[])
    result=revisions.run_due_revisions(output_dir='none',as_of=date(2026,10,1),bar_fetcher=lambda *args:pytest.fail('premature fetch'))
    assert result['awaiting_maturity']==1 and result['new_revisions']==0


def test_activation_is_append_only_and_reversible(monkeypatch,tmp_path):
    import sqlite3
    path=tmp_path/'operational.sqlite3'
    monkeypatch.setattr(revisions.trade_backtest_store,'_path',lambda:path)
    rows=[];originals=[]
    for i in range(76):
        original=saved(report_filename=f'{i}.html',status='insufficient_data',reason='missing_ohlc')
        originals.append(original)
        rows.append({'scope_id':str(i),'report_filename':f'{i}.html','horizon_trading_days':10,'generated_date':'2026-09-05','original_payload_sha256':revisions.digest(original),'sessions':['2026-09-07'],'maturity_date':'2026-09-07'})
    monkeypatch.setattr(revisions.trade_backtest_store,'list_results',lambda **kw:originals)
    by_filename = {item['report_filename']: item for item in originals}
    def exact_result(*, report_filename, horizon_trading_days):
        assert horizon_trading_days == 10
        return by_filename.get(report_filename)
    monkeypatch.setattr(revisions.trade_backtest_store, 'get_result', exact_result)
    monkeypatch.setattr(revisions,'session_window',lambda *a:{'status':'verified','sessions':['2026-09-07'],'maturity_date':'2026-09-07'})
    manifest={'schema_version':'legacy-revision-scope-v1','authorized_by':'explicit test approval','batch_id':'test','rows':rows}
    revisions.activate_scope(manifest);revisions.activate_scope(manifest)
    assert revisions.revision_summary()['approved_scope_count']==76
    payload={'state':'insufficient_data','bars':[]}
    assert revisions.append_revision('test','0','2026-10-02',payload)
    assert not revisions.append_revision('test','0','2026-10-02',payload)
    assert not revisions.append_revision('test','0','2026-10-02',{'state':'no_trade'})
    revisions.deactivate_batch('test')
    assert revisions.active_manifests()==[]
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM trade_evidence_revisions_v1').fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='trade_evaluation_results_v1'").fetchone()[0]==0


def test_scope_change_aborts_before_database_creation(monkeypatch,tmp_path):
    path=tmp_path/'operational.sqlite3';monkeypatch.setattr(revisions.trade_backtest_store,'_path',lambda:path)
    manifest={'schema_version':'legacy-revision-scope-v1','authorized_by':'test','batch_id':'x','rows':[{'scope_id':str(i),'report_filename':f'{i}.html','horizon_trading_days':10,'original_payload_sha256':'wrong'} for i in range(76)]}
    monkeypatch.setattr(revisions.trade_backtest_store,'list_results',lambda **kw:[])
    with pytest.raises(ValueError):revisions.activate_scope(manifest)
    assert not path.exists()


@pytest.mark.parametrize("initial_source_missing", [False, True])
def test_due_revision_archives_raw_and_never_saves_original(monkeypatch,tmp_path,initial_source_missing):
    import mode_trade_backtest,report_history_storage,report_artifacts,trade_path_backtest
    original=saved(status='insufficient_data',reason='missing_ohlc')
    scope={'scope_id':'one','report_filename':DISPUTED_FILENAME,'ticker':'2382.TW','generated_date':'2026-09-05','maturity_date':'2026-09-18','sessions':['2026-09-18'],'original_payload_sha256':revisions.digest(original)}
    path=tmp_path/'revision.sqlite3'
    import sqlite3
    with sqlite3.connect(path) as c:c.execute('CREATE TABLE trade_evidence_revisions_v1(batch_id,scope_id,as_of_session,state)')
    monkeypatch.setattr(revisions,'_connect',lambda:sqlite3.connect(path))
    monkeypatch.setattr(revisions,'active_manifests',lambda:[{'batch_id':'test','rows':[scope]}])
    monkeypatch.setattr(revisions,'session_window',lambda *a:{'status':'verified','sessions':['2026-09-18']})
    monkeypatch.setattr(revisions.trade_backtest_store,'list_results',lambda **kw:[original])
    def exact_result(*, report_filename, horizon_trading_days):
        assert report_filename == original['report_filename'] and horizon_trading_days == 10
        return original
    monkeypatch.setattr(revisions.trade_backtest_store, 'get_result', exact_result)
    monkeypatch.setattr(revisions.trade_backtest_store,'save_result',lambda *a:pytest.fail('original must never save'))
    monkeypatch.setattr(mode_trade_backtest,'_parsed_snapshot',lambda *a:{})
    monkeypatch.setattr(mode_trade_backtest,'_plan_inputs',lambda *a:({'direction':'Long'},(5,10),'') )
    monkeypatch.setattr(mode_trade_backtest,'_execution_context',lambda *a:{})
    class Storage:
        def get_report(self,key):
            class Item:content=b'{"data": {"source": "legacy"}}'
            return Item()
    monkeypatch.setattr(report_history_storage,'storage_for_existing_output_dir',lambda *a:Storage())
    monkeypatch.setattr(report_artifacts.ReportArtifactLocator,'require_key',lambda *a,**kw:'resolved-nested-key')
    monkeypatch.setattr(trade_path_backtest,'evaluate_trade_path',lambda **kw:{'status':'insufficient_data','reason':'basis_unknown','strategy_roi_pct':None})
    import maturity_source_admission
    monkeypatch.setattr(maturity_source_admission,"assess_maturity_source",lambda *a:{"eligible":True,"finality_guaranteed":False,"reason":"isolated source-contract fixture"})
    receipt=[]
    monkeypatch.setattr(revisions,'append_revision',lambda *args:receipt.append(args[-1]) or True)
    def fetch(ticker,start,end):
        assert end==date(2026,9,18);return [{'date':'2026-09-18','close':343}]
    if initial_source_missing:
        monkeypatch.setattr(maturity_source_admission, 'assess_maturity_source', lambda *a: {'eligible':False,'reason':'official_price_raw_evidence_invalid'})
        for _ in range(2):
            waiting=revisions.run_due_revisions(output_dir='nested',as_of=date(2026,9,18),bar_fetcher=fetch)
            assert waiting['awaiting_source_evidence']==1 and waiting['already_attempted_session']==0
            assert waiting['new_revisions']==0 and not receipt and not waiting['errors']
        monkeypatch.setattr(maturity_source_admission, 'assess_maturity_source', lambda *a: {'eligible':True,'finality_guaranteed':False})
    result=revisions.run_due_revisions(output_dir='nested',as_of=date(2026,9,18),bar_fetcher=fetch)
    assert result['new_revisions']==1 and not result['errors']
    assert receipt[0]['bars'][0]['close']==343 and receipt[0]['original_row_unchanged']
    assert not receipt[0]['point_in_time_verified'] and not receipt[0]['strategy_validated']
