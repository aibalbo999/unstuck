import copy
import json
from pathlib import Path
from trade_price_reference import price_reference_issues, snapshot_price_reference_issues


def catalog():
    return {'short_term_market_context': {'daily_market_data': {'availability':'available','source':'fixture','as_of':'2026-10-07','price_adjustment_basis':'fixture adjusted','bars':[{'date':'2026-09-11','low':846,'high':930,'close':900}]}}}


def payload():
    return {'support_level':'846','resistance_level':'930','support_source_refs':['short_term_market_context.daily_market_data.bars[0].low'],'resistance_source_refs':['short_term_market_context.daily_market_data.bars[0].high']}


def test_exact_historical_prices_are_allowed():
    assert price_reference_issues(payload(), catalog()) == []


def test_both_numeric_contradictions_are_rejected_without_replacement():
    p=payload();p['support_level']='889';p['resistance_level']='922';before=copy.deepcopy(p)
    assert price_reference_issues(p,catalog()) == ['support_level_source_value_mismatch','resistance_level_source_value_mismatch']
    assert p == before


def test_missing_or_invalid_reference_is_not_claimed_as_proven_mismatch():
    p=payload();p['support_source_refs']=['short_term_market_context.daily_market_data.bars[9].low']
    assert price_reference_issues(p,catalog()) == ['support_level_source_observation_unverified']


def test_prose_or_range_does_not_pretend_to_be_direct_quote():
    p=payload();p['support_level']='分析區間 840–850'
    assert price_reference_issues(p,catalog()) == ['support_level_source_scalar_unverified']


def test_real_6409_original_bound_catalog():
    root=Path(__file__).resolve().parent
    s=json.loads((root/'fixtures/trade_price_reference_6409.json').read_text())
    assert snapshot_price_reference_issues(s) == ['support_level_source_value_mismatch','resistance_level_source_value_mismatch']
    s['analysis_evidence']['sections']['trade_source_manifest']['data']['catalog']['short_term_market_context']['daily_market_data']['bars'][0]['low']=846
    assert snapshot_price_reference_issues(s) == []


def test_real_snapshot_gate_and_daily_withdrawal():
    from evidence_exit_gate import evaluate_report_evidence
    from daily_decision_dashboard import build_daily_decision_dashboard
    root=Path(__file__).resolve().parent
    s=json.loads((root/'fixtures/trade_price_reference_6409.json').read_text())
    md='支撐位：846；壓力位：930。觀望，不是下單許可。'
    gate=evaluate_report_evidence(md,s)
    assert gate['verdict']=='rejected'
    assert not gate['source_admission']['eligible']
    row={'ticker':'6409.TW','filename':'6409_TW_v4_report_job_e40bd581fa03.html','pipeline_id':'v4','content_credibility':{'status':'passed'},'report_conformance':{'status':'passed'},'evidence_exit_gate':gate}
    d=build_daily_decision_dashboard(reports={'reports':[row]},watchlist={},screener={'items':[{'ticker':'6409.TW','score':99}]},performance={},free_mode={},quality_audit={'scope':'all_indexed_reports','selection_basis':'latest_per_ticker_pipeline','current_blocked_reports':[row]})
    assert any(r['ticker']=='6409.TW' for r in d['withdrawn_reports'])
    assert all(r['ticker']!='6409.TW' for r in d['top_candidates'])


def typed_payload(kind='direct_reference', operation='identity'):
    p=payload()
    p['price_level_evidence']=[{'field':field,'kind':kind,'operation':operation,'inputs':[{'ref':p[role][0],'observed_date':'2026-09-11','window_sessions':1,'price_basis':None}]} for field,role in [('support_level','support_source_refs'),('resistance_level','resistance_source_refs')]]
    return p


def test_typed_direct_quote_and_metadata():
    assert price_reference_issues(typed_payload(),catalog()) == []


def test_date_period_and_price_scope_are_not_numeric_match():
    p=typed_payload();p['price_level_evidence'][0]['inputs'][0].update(observed_date='2026-10-07',window_sessions=52,price_basis='exchange raw')
    c=catalog();c['short_term_market_context']['daily_market_data']['price_adjustment_basis']='adjusted'
    assert price_reference_issues(p,c)==['support_level_source_date_mismatch','support_level_source_period_mismatch','support_level_source_scope_mismatch']


def test_reproducible_derived_price_is_not_required_to_equal_an_input():
    p=typed_payload();refs=[p['support_source_refs'][0],p['resistance_source_refs'][0]]
    p['support_source_refs']=refs;p['support_level']='888'
    p['price_level_evidence'][0]={'field':'support_level','kind':'derived','operation':'mean','inputs':[{'ref':ref,'observed_date':'2026-09-11','window_sessions':1} for ref in refs]}
    assert price_reference_issues(p,catalog())==[]
    p['support_level']='846'
    assert price_reference_issues(p,catalog())==['support_level_source_value_mismatch']


def test_derived_label_without_reproducible_formula_cannot_bypass_gate():
    p=typed_payload('derived','invented');p['support_level']='888'
    assert 'support_level_source_derivation_unverified' in price_reference_issues(p,catalog())


def test_unknown_basis_is_unverified_and_never_declared_mismatch():
    p=typed_payload();p['price_level_evidence'][0]['inputs'][0]['price_basis']='exchange raw'
    c=catalog();c['short_term_market_context']['daily_market_data'].pop('price_adjustment_basis')
    assert price_reference_issues(p,c)==['support_level_source_scope_unverified']


def test_sma_window_and_rounding_are_checked():
    p=typed_payload();ref='short_term_market_context.technical_indicators.sma_20';p['support_source_refs']=[ref];p['support_level']='846'
    p['price_level_evidence'][0]['inputs']=[{'ref':ref,'observed_date':'2026-10-07','window_sessions':20}]
    c=catalog();c['short_term_market_context']['technical_indicators']={'availability':'available','source':'fixture','as_of':'2026-10-07','sma_20':846.123}
    assert price_reference_issues(p,c)==[]
    p['price_level_evidence'][0]['inputs'][0]['window_sessions']=5
    assert price_reference_issues(p,c)==['support_level_source_period_mismatch']


def test_typed_fields_survive_runtime_normalization():
    from structured_output_normalize_dispatch import normalize_structured_output
    from test_trade_source_completion import setup_payload
    raw=setup_payload();raw['price_level_evidence']=typed_payload()['price_level_evidence']
    normalized=normalize_structured_output(24,raw)
    assert normalized['price_level_evidence']==raw['price_level_evidence']


def test_formal_get_routes_use_original_catalog_and_preserve_snapshot(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import report_index
    import api_routes.watchlist as routes
    from data_trust import data_snapshot_filename_for_report
    from report_quality_audit import build_historical_indexed_report_quality_audit
    monkeypatch.setattr(report_index,'CACHE_DB_PATH',str(tmp_path/'index.sqlite3'))
    fixture=Path(__file__).resolve().parent/'fixtures/trade_price_reference_6409.json'
    original=fixture.read_text();name='6409_TW_v4_report_job_e40bd581fa03.html'
    artifact=tmp_path/data_snapshot_filename_for_report(name)
    artifact.write_text(original)
    (tmp_path/name).write_text('<html>original</html>')
    (tmp_path/name.replace('.html','.md')).write_text('支撐位：846；壓力位：930。觀望，不是下單許可。')
    assert report_index.upsert_report_metadata(name,output_dir=str(tmp_path))
    monkeypatch.setattr(routes.report_history_service,'list_reports',lambda **kw:{'reports':[]})
    monkeypatch.setattr(routes.watchlist_service,'list_watchlist_with_report_alerts',lambda *a,**kw:{'items':[]})
    monkeypatch.setattr(routes.market_screener,'list_auto_screener_watchlist',lambda *a,**kw:{'items':[{'ticker':'6409.TW','score':99}]})
    monkeypatch.setattr(routes.decision_tracking_service,'compute_tracking_performance_stats',lambda *a:{})
    monkeypatch.setattr(routes.job_observability,'build_ops_dashboard_snapshot',lambda **kw:{})
    monkeypatch.setattr(routes,'get_delivery_audit_summary',lambda:{})
    app=FastAPI();app.include_router(routes.create_watchlist_router(routes.WatchlistRouteDeps(get_output_dir=lambda:str(tmp_path),get_task_queue=lambda:None,run_stock_analysis_job=lambda *a:'unused',create_job=lambda *a:'unused',find_active_job=lambda *a:{},require_mutation_authorized=lambda r:None)))
    client=TestClient(app)
    for _ in range(2):
        quality=client.get('/api/watchlist/current-quality-summary');assert quality.status_code==200
        item=next(r for r in quality.json()['items'] if r['ticker']=='6409.TW')
        assert item['evidence_exit_gate_verdict']=='rejected'
        daily=client.get('/api/watchlist/daily-dashboard');assert daily.status_code==200
        d=daily.json();assert any(r['ticker']=='6409.TW' for r in d['withdrawn_reports'])
        assert all(r['ticker']!='6409.TW' for r in d['top_candidates'])
    historical=build_historical_indexed_report_quality_audit(str(tmp_path))
    assert historical['current_blocked_reports']==[]
    assert artifact.read_text()==original


def test_derived_inputs_with_unknown_or_different_price_basis_are_unverified():
    p=typed_payload();p['support_level']='888';refs=[p['support_source_refs'][0],p['resistance_source_refs'][0]]
    p['support_source_refs']=refs;p['price_level_evidence'][0]={'field':'support_level','kind':'derived','operation':'mean','inputs':[{'ref':ref} for ref in refs]}
    c=catalog();c['short_term_market_context']['daily_market_data'].pop('price_adjustment_basis')
    assert price_reference_issues(p,c)==['support_level_source_derivation_scope_unverified']


def test_new_contract_requires_typed_field_and_schema_exposes_formula():
    from trade_source_contract import missing_trade_fields,CONTRACT_VERSION
    from structured_output_risk_models import SwingTradeSetup
    from test_trade_source_completion import setup_payload
    p=setup_payload();context={'_trade_source_manifest':{'version':CONTRACT_VERSION}}
    assert 'price_level_evidence' in missing_trade_fields(p,context=context)
    p['price_level_evidence']=[]
    assert 'price_level_evidence' not in missing_trade_fields(p,context=context)
    assert SwingTradeSetup.model_json_schema()['$defs']['PriceLevelEvidence']['properties']['kind']['enum']==['direct_reference','derived']


def test_runtime_contract_keeps_typed_proof_and_degrades_proven_mismatch():
    from trade_source_contract import bind_trade_payload,CONTRACT_VERSION
    from test_trade_source_completion import setup_payload
    p=setup_payload();p.update(typed_payload());p.update(trade_direction='Neutral',entry_zone='N/A',target_price='N/A',stop_loss='N/A',core_catalyst='等待確認後再重新評估',catalyst_source_refs=[])
    context={'data':{},'_trade_source_manifest':{'version':CONTRACT_VERSION,'visible':True,'catalog':catalog(),'fingerprint':'fixture'}}
    _,assessment=bind_trade_payload(p,context)
    assert assessment['status']=='observation'
    assert assessment['price_reference_checks'][0]['kind']=='direct_reference'
    p['support_level']='889';_,assessment=bind_trade_payload(p,context)
    assert assessment['status']=='degraded'
    assert assessment['price_reference_checks'][0]['status']=='mismatch'
    assert 'support_level_source_value_mismatch' in assessment['reason_codes']


def test_unknown_original_lineage_is_caution_not_false_verified_or_mismatch():
    from trade_price_reference import snapshot_price_reference_checks
    root=Path(__file__).resolve().parent
    s=json.loads((root/'fixtures/trade_price_reference_6409.json').read_text())
    s['analysis_evidence']['sections']['trade_source_manifest']['data']['fingerprint']='invalid'
    checks=snapshot_price_reference_checks(s)
    assert all(c['status']=='unverifiable' for c in checks)
    assert snapshot_price_reference_issues(s)==[]
    from evidence_exit_gate import evaluate_report_evidence
    gate=evaluate_report_evidence('觀望',s)
    assert gate['verdict']=='caution'
    assert gate['source_admission']['source_eligible'] is False
    assert 'support_level_source_lineage_unverified' in gate['source_admission']['source_warnings']
