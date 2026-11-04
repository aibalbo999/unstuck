"""Undefined P/E never supplies a number or bypasses evidence consumers."""
from copy import deepcopy
from datetime import date

import pytest

from test_peer_reference_evidence import evidence_environment, DAY


def row_with_proof():
    from data_fetch.market_sources.peers import PEER_METRIC_FIELDS
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    row = {key: 1.0 for key in PEER_METRIC_FIELDS}
    row.update(ticker='6230.TW', name='尼得科超眾', pe_ttm=None,
        pe_applicability_evidence=collect_reference_income('6230.TW', '2026-11-04', today=DAY),
        metric_applicability={key:'applicable' for key in PEER_METRIC_FIELDS},
        metric_sources={key: {'provider':'fixture source','observed_at':'2026-06-30',
            'basis':'annual_revenue / same_date_year_end_assets' if key == 'asset_turnover' else 'fixture'}
            for key in PEER_METRIC_FIELDS if key != 'pe_ttm'},
        missing_metrics=['pe_ttm'], metrics_status='partial')
    return row


def test_complete_applicable_fields_require_the_entire_live_nonpositive_income_proof(evidence_environment):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from thermal_peer_source_refresh import _usable_metrics
    from data_trust_audit import source_record_count
    row = row_with_proof()
    reassess_reference_applicability(row, today=DAY)
    assert row['pe_ttm'] is None and 'pe_ttm' not in row['metric_sources']
    assert row['metrics_status'] == 'complete' and row['missing_metrics'] == []
    assert _usable_metrics(row, DAY) is True
    assert source_record_count('dynamic_peer_metrics', {'dynamic_peer_metrics':[row]}) == 1


def test_another_missing_field_stays_partial_and_warning_is_not_hidden(evidence_environment):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    row = row_with_proof(); row['gross_margin_pct'] = None; row['metric_sources'].pop('gross_margin_pct')
    reassess_reference_applicability(row, today=DAY)
    assert row['metrics_status'] == 'partial' and row['missing_metrics'] == ['gross_margin_pct']


def test_expired_or_forged_reason_is_rejected_by_merge_count_and_delivery(evidence_environment):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from thermal_peer_source_refresh import _usable_metrics
    from data_trust_audit import source_record_count
    row = row_with_proof(); reassess_reference_applicability(row, today=DAY)
    evidence_environment[0].clear()
    with pytest.raises(ValueError): _usable_metrics(row, DAY)
    assert source_record_count('dynamic_peer_metrics', {'dynamic_peer_metrics':[row]}) == 0
    reassess_reference_applicability(row, today=DAY)
    assert row['metrics_status'] == 'partial' and row['missing_metrics'] == ['pe_ttm']
    assert row['metric_applicability']['pe_ttm'] == 'applicable'


def test_private_original_paths_are_not_prompted_and_original_is_unchanged(evidence_environment):
    import json
    from prompt_evidence import prompt_evidence_copy
    row = row_with_proof(); before = deepcopy(row)
    public = json.dumps(prompt_evidence_copy(row), ensure_ascii=False)
    assert 'raw_response_path' not in public and 'net_income_twd' not in public
    assert row == before and 'source_record_archive' in row['pe_applicability_evidence']


def test_normal_fallback_uses_existing_cache_before_any_new_reference_request(evidence_environment, monkeypatch):
    from data_fetch.market_sources import peer_recovery, official_peer_valuation, taiwan
    store, calls, _ = evidence_environment
    monkeypatch.setattr(taiwan, 'DataLoader', None)
    monkeypatch.setattr(official_peer_valuation, 'fetch_official_peer_valuation', lambda *a, **kw: {
        'metrics': {'pb':1.47}, 'status':'success', 'source':official_peer_valuation.PROVIDER,
        'official_company_name':'尼得科超眾', 'observed_at':'2026-11-04'})
    result = peer_recovery.fetch_peer_valuation_fallback('6230.TW', today=DAY)
    assert result['metrics'] == {'pb':1.47} and 'pe_applicability_evidence' in result
    before = deepcopy(store); acquisitions = len(calls)
    warm = peer_recovery.fetch_peer_valuation_fallback('6230.TW', today=DAY)
    assert warm['cache_hit'] is True and len(calls) == acquisitions and store == before
    # Loss of one independent raw owner removes the reason from delivery only.
    key = next(key for key in store if key.startswith('shared_provider:'))
    store.pop(key); before = deepcopy(store)
    stale = peer_recovery.fetch_peer_valuation_fallback('6230.TW', today=DAY)
    assert stale['metrics'] == {'pb':1.47} and 'pe_applicability_evidence' not in stale
    assert store == before and len(calls) == acquisitions


def test_a_positive_numeric_fallback_never_launches_the_missing_pe_source(evidence_environment, monkeypatch):
    from data_fetch.market_sources import peer_recovery, official_peer_valuation, taiwan
    monkeypatch.setattr(taiwan, 'DataLoader', None)
    monkeypatch.setattr(official_peer_valuation, 'fetch_official_peer_valuation', lambda *a, **kw: {
        'metrics': {'pb':1.47,'pe_ttm':20}, 'status':'success', 'source':official_peer_valuation.PROVIDER,
        'official_company_name':'尼得科超眾', 'observed_at':'2026-11-04'})
    result = peer_recovery.fetch_peer_valuation_fallback('6230.TW', today=DAY)
    assert result['metrics']['pe_ttm'] == 20 and not evidence_environment[1]


@pytest.mark.parametrize('sdk_pe', [None, -20, 0])
def test_peer_loop_preserves_issuer_and_undefined_value_through_normal_delivery(evidence_environment, monkeypatch, sdk_pe):
    from data_fetch.market_sources import peers, official_peer_valuation, taiwan
    monkeypatch.setattr(peers, '_today', lambda:DAY)
    monkeypatch.setattr(taiwan, 'DataLoader', None)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda:[])
    monkeypatch.setattr(peers, 'resolve_legacy_peer_candidates', lambda *a, **kw:([
        {'ticker':'6230.TW','name':'尼得科超眾','identity_status':'master_verified',
         'comparison_status':'industry_candidate_only','industry_categories':['電腦及週邊設備業']}],
        {'selection_status':'selected','selection_rejected_reason_counts':{}}))
    monkeypatch.setattr(peers.yf, 'Ticker', lambda symbol:type('Quote', (), {'info':{
        'symbol':symbol,'quoteType':'EQUITY','industry':'Electronic Components',
        'trailingPE':sdk_pe,
        'grossMargins':.2,'operatingMargins':.1,'profitMargins':.05,'returnOnEquity':.1,
        'totalRevenue':100,'totalAssets':200,'priceToSalesTrailing12Months':3}})())
    monkeypatch.setattr(official_peer_valuation, 'fetch_official_peer_valuation', lambda *a, **kw: {
        'metrics': {'pb':1.47}, 'status':'success', 'source':official_peer_valuation.PROVIDER,
        'official_company_name':'尼得科超眾', 'observed_at':'2026-11-04'})
    result = peers.fetch_dynamic_peer_metrics_with_diagnostics('1234.TWO', 'fixture target',
        'Technology', 'Electronic Components', {})
    assert len(result['peers']) == 1
    row = result['peers'][0]
    assert row['ticker'] == '6230.TW' and row['pe_ttm'] is None
    assert row['metrics_status'] == 'complete' and result['audit']['coverage_status'] == 'success'


@pytest.mark.parametrize('target_pe', [-5, 0, '-10x'])
def test_nonpositive_pe_cannot_create_false_discount_or_peer_median(target_pe):
    from stock_snapshot.peers_valuation import _peer_comparison
    result = _peer_comparison({'ticker':'3324.TWO', 'pe_ratio_raw':target_pe,
        'dynamic_peer_metrics':[
            {'ticker':'6230.TW', 'name':'尼得科超眾','pe_ttm':None,'gross_margin_pct':10},
            {'ticker':'0001.TW','pe_ttm':-20,'gross_margin_pct':5},
            {'ticker':'0002.TW','pe_ttm':0,'gross_margin_pct':7},
            {'ticker':'0003.TW','pe_ttm':20,'gross_margin_pct':15}]})
    assert result['summary']['peer_count'] == 4
    assert result['summary']['peer_pe_median'] == 20
    assert result['summary']['valuation_label'] == '同業資料不足'
    assert result['target']['pe_ttm'] is None
