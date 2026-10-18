from test_official_thermal_peer_cohort import replay_acquisition_day
"""Normal core collection must retain the thermal provider's partial status."""
import pytest

from test_official_thermal_peer_cohort import Stock, TICKER, TODAY, native_boundary, isolated_cache


@pytest.mark.parametrize('missing_pe', [True, False])
def test_normal_core_keeps_thermal_metric_coverage_and_original_provenance(monkeypatch, missing_pe):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.market_sources import peers
    import source_applicability

    calls = native_boundary(monkeypatch)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers, 'fetch_peer_valuation_fallback', lambda *a, **k: {'metrics': {}, 'status': 'metrics_missing'})
    monkeypatch.setattr(source_applicability, 'source_is_applicable', lambda source, _: source == 'dynamic_peer_metrics')

    class QuotedStock(Stock):
        @property
        def info(self):
            value = super().info
            if missing_pe and self.symbol == '6230.TW':
                value['trailingPE'] = None
            return value

    monkeypatch.setattr(peers.yf, 'Ticker', QuotedStock)
    result = sync.fetch_sync_enrichment_bundle(
        ticker=TICKER, stock=object(), company_name='雙鴻', sector='Technology',
        industry='Computer Hardware', company_identity={}, years=[], net_income_history=[],
        shares_outstanding=None, skip_optional_http=True)
    assert len(calls) == 4 and len(result['dynamic_peer_metrics']) == 5
    audits = [a for a in result['audit'] if a['source'] == 'dynamic_peer_metrics']
    assert len(audits) == 1
    audit = audits[0]
    assert audit['status'] == ('degraded_enrichment' if missing_pe else 'success')
    assert audit['coverage_status'] == ('partial' if missing_pe else 'success')
    assert audit['usable_count'] == audit['record_count'] == 5
    assert len(audit['provider_attempts']) == 1
    assert audit['official_thermal_candidate_details']['http_request_count'] == 4
    assert all(row['business_comparability_verified_current'] is False for row in result['dynamic_peer_metrics'])
