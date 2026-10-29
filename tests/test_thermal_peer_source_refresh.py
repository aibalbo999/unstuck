from test_official_thermal_peer_cohort import replay_acquisition_day
"""Source-only thermal metric repair preserves existing claims and core ages."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import time

import pytest

from test_official_thermal_peer_cohort import Stock, TICKER, TODAY, native_boundary, isolated_cache


def saved_report(storage):
    from report_analysis_evidence import capture_analysis_evidence
    from report_persistence import report_bundle_keys_for_filename
    filename = '3324_TWO_v4_report_20261013_090000.html'
    keys = report_bundle_keys_for_filename(filename)
    epoch = time.time() - 3 * 86400
    audit = [{'source': 'market_data', 'provider': 'original market', 'status': 'success',
              'record_count': 1, 'fetched_at_epoch': epoch,
              'fetched_at': datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
              'fetch_id': 'original', 'cache_hit': False, 'stale': True},
             {'source': 'dynamic_peer_metrics', 'provider': 'FinMind/yfinance',
              'status': 'unavailable', 'record_count': 0, 'fetched_at_epoch': epoch, 'fetch_id': 'original'}]
    data = {'ticker': TICKER, 'company_name': '雙鴻 / Auras Technology Co., Ltd.',
            'instrument_type': 'EQUITY', 'sector': 'Technology', 'industry': 'Computer Hardware',
            'current_price': 100, 'years': ['2021', '2022', '2023', '2024', '2025'],
            'revenue_history': [1, 2, 3, 4, 5], 'dynamic_peer_metrics': [],
            'peer_discovery_results': [{'title': 'Original broad candidate'}], 'source_audit': deepcopy(audit)}
    snapshot = {'ticker': TICKER, 'company_name': data['company_name'], 'pipeline': 'v4',
                'generated_at': datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
                'data': data, 'source_audit': audit}
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        snapshot[gate] = {'original': gate}
    snapshot['analysis_evidence'] = capture_analysis_evidence({'data': data}, generated_at=snapshot['generated_at'])
    storage.save_report(keys.html_key, b'<html>unchanged conclusions</html>', content_type='text/html')
    storage.save_report(keys.md_key, b'unchanged conclusions', content_type='text/markdown')
    storage.save_report(keys.data_key, json.dumps(snapshot).encode(), content_type='application/json')
    return filename, keys, snapshot


def test_public_source_refresh_acquires_thermal_metrics_without_core_or_model_calls(monkeypatch, tmp_path):
    from data_fetch.market_sources import peers
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    native_boundary(monkeypatch)
    # The historical replay already freezes time.time; keep this consumer's
    # datetime clock on the same acquisition day without relaxing live expiry.
    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(time.time(), tz)
    monkeypatch.setattr('thermal_peer_source_refresh.datetime', ReplayClock)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    storage = InMemoryStorage(); filename, keys, old = saved_report(storage)
    def forbidden(*a, **k): pytest.fail('Source refresh must not call unrelated data or models')
    service = StockDataService(registry=ProviderRegistry([
        DynamicPeerMetricsProvider(), CallableProvider('market_data', 'forbidden core', forbidden)]))
    response = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
        refresh_service=service, source='dynamic_peer_metrics', return_refreshed_data=True))
    updated = json.loads(storage.get_report(keys.data_key).content)
    assert len(updated['data']['dynamic_peer_metrics']) == 5
    assert response['refresh_sources'] == ['dynamic_peer_metrics']
    for key in ('current_price', 'revenue_history', 'years', 'peer_discovery_results'):
        assert updated['data'][key] == old['data'][key]
    assert next(a for a in updated['source_audit'] if a['source'] == 'market_data') == old['source_audit'][0]
    assert updated['analysis_evidence'] == old['analysis_evidence']
    for gate in ['report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert updated[gate] == old[gate]
    assert storage.get_report(keys.html_key).content == b'<html>unchanged conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'unchanged conclusions'
    assert response['analysis_text_stale'] is True
    observed = events()
    assert observed and all(r['source'] == 'dynamic_peer_metrics' for r in observed)


@pytest.mark.parametrize('change', ['wrong_target', 'wrong_company', 'not_equity', 'missing_list'])
def test_source_refresh_rejects_inconsistent_original_context_without_fetch(monkeypatch, tmp_path, change):
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from fastapi import HTTPException
    storage = InMemoryStorage(); filename, keys, old = saved_report(storage)
    if change == 'wrong_target': old['data']['ticker'] = '3017.TW'
    elif change == 'wrong_company': old['data']['company_name'] = '另一家公司'
    elif change == 'not_equity': old['data']['instrument_type'] = 'ETF'
    elif change == 'missing_list': old['data'].pop('dynamic_peer_metrics')
    original = json.dumps(old).encode()
    storage.save_report(keys.data_key, original, content_type='application/json')
    service = StockDataService()
    async def forbidden(*a, **k): pytest.fail('Invalid context must not fetch')
    monkeypatch.setattr(service, 'fetch_source_async', forbidden)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
            refresh_service=service, source='dynamic_peer_metrics'))
    assert raised.value.status_code == 400
    assert storage.get_report(keys.data_key).content == original


@pytest.mark.parametrize('change', ['missing_receipt', 'peer_tampered', 'valuation_upgrade', 'duplicate_peer',
                                  'nonfinite', 'bool_metric', 'unknown_period', 'future_period', 'missing_provenance',
                                  'bad_count', 'bool_count', 'expired_audit', 'wrong_provider', 'fresh_cache'])
def test_unverified_metric_payload_cannot_mutate_saved_source(monkeypatch, change):
    from data_fetch.market_sources import peers
    from thermal_peer_source_refresh import merge_thermal_peer_source
    from storage.report_storage import InMemoryStorage
    from fastapi import HTTPException
    native_boundary(monkeypatch)
    monkeypatch.setattr(peers, '_today', lambda: TODAY)
    monkeypatch.setattr(peers, 'load_peer_stock_master', lambda: [])
    monkeypatch.setattr(peers.yf, 'Ticker', Stock)
    rows = peers.fetch_dynamic_peer_metrics_with_diagnostics(TICKER, '雙鴻', 'Technology', 'Computer Hardware', {})['peers']
    audit = {'source': 'dynamic_peer_metrics', 'provider': 'FinMind/yfinance', 'status': 'success',
             'fetch_id': 'new', 'record_count': 5, 'usable_count': 5, 'stale': False, 'fetched_at_epoch': time.time()}
    if change == 'missing_receipt': rows[0].pop('thermal_membership_originals')
    elif change == 'peer_tampered': rows[0]['ticker'] = '2330.TW'
    elif change == 'valuation_upgrade': rows[0]['business_comparability_verified_current'] = True
    elif change == 'duplicate_peer': rows[1] = deepcopy(rows[0])
    elif change == 'nonfinite': rows[0]['gross_margin_pct'] = float('nan')
    elif change == 'bool_metric': rows[0]['gross_margin_pct'] = True
    elif change == 'unknown_period': rows[0]['metric_sources']['asset_turnover']['observed_at'] = None
    elif change == 'future_period': rows[0]['metric_sources']['asset_turnover']['observed_at'] = '2099-12-31'
    elif change == 'missing_provenance': rows[0]['metric_sources'].pop('gross_margin_pct')
    elif change == 'bad_count': audit['record_count'] = 10
    elif change == 'bool_count': audit['record_count'] = True
    elif change == 'expired_audit': audit['fetched_at_epoch'] = time.time() - 1801
    elif change == 'wrong_provider': audit['provider'] = 'other'
    elif change == 'fresh_cache': audit.update(status='skipped_fresh_cache', cache_hit=True)
    storage = InMemoryStorage(); _, _, old = saved_report(storage); before = deepcopy(old)
    with pytest.raises(HTTPException) as raised:
        merge_thermal_peer_source(old['data'], old['source_audit'], rows, [audit], TICKER)
    assert raised.value.status_code == 502 and old == before
