"""Public boundary checks. Original private-data replay cases remain local."""
import asyncio, json, time
from copy import deepcopy
from datetime import datetime
import pytest
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import init_db
from storage.report_storage import InMemoryStorage
from report_refresh_service import refresh_report_data_snapshot
NOW = datetime.fromisoformat('2026-10-05T23:00:00+08:00').timestamp()

@pytest.fixture
def fixed(monkeypatch):
    monkeypatch.setattr(time, 'time', lambda: NOW)

def report():
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    old['data']['company_identity'] = {'ticker': '6214.TW', 'stock_id': '6214', 'instrument_type': 'EQUITY', 'official_name': '精誠'}
    old['data']['institutional_trading'] = {'latest_date': '2026-10-02', 'original_limited_observation': True}
    old['source_audit'].append({'source': 'institutional_trading', 'provider': 'FinMind', 'status': 'degraded_enrichment', 'record_count': 10, 'fetched_at_epoch': NOW - 86400, 'fetch_id': 'old-institutional'})
    old['data']['source_audit'] = deepcopy(old['source_audit'])
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    return (storage, filename, keys, old)

def test_nontrading_weekday_before_cutoff_can_use_last_completed_session(monkeypatch):
    from institutional_source_refresh import institutional_refresh_session
    monkeypatch.setattr(time, 'time', lambda: datetime.fromisoformat('2026-10-05T20:00:00+08:00').timestamp())
    monkeypatch.setattr('data_freshness_market.market_calendar', lambda *a, **k: {'coverage_status': 'available', 'holidays': {datetime(2026, 10, 5).date()}})
    assert institutional_refresh_session('6214.TW') == '2026-10-02'

@pytest.mark.parametrize('ticker', ['6214.TW', '6152.TWO'])
@pytest.mark.parametrize('moment,expected', [('2026-10-05T20:00:00+08:00', '2026-10-02'), ('2026-10-05T23:00:00+08:00', '2026-10-05'), ('2026-10-04T12:00:00+08:00', '2026-10-02')])
def test_refresh_uses_the_providers_mature_market_session(monkeypatch, ticker, moment, expected):
    from institutional_source_refresh import institutional_refresh_session
    seen = []

    def calendar(value, **kwargs):
        seen.append(value)
        return {'coverage_status': 'available', 'holidays': set()}
    monkeypatch.setattr(time, 'time', lambda: datetime.fromisoformat(moment).timestamp())
    monkeypatch.setattr('data_freshness_market.market_calendar', calendar)
    assert institutional_refresh_session(ticker) == expected
    assert seen == [ticker]

def _assert_snapshot_integrity(snapshot):
    from data_trust_snapshot_integrity import verify_data_snapshot_integrity, snapshot_size_bytes
    assert verify_data_snapshot_integrity(snapshot)['valid'] is True
    assert snapshot['content_hash'] == snapshot['snapshot_hash']
    assert snapshot['reproducibility_packet']['data_snapshot_hash'] == snapshot['snapshot_hash']
    assert snapshot['snapshot_size_bytes'] == snapshot_size_bytes(snapshot)

def test_legacy_without_analysis_completeness_does_not_invent_success(fixed, tmp_path):
    init_db()
    storage, name, keys, old = report()
    assert 'analysis_completeness' not in old and 'oos_evaluation_inputs' not in old
    data = deepcopy(old['data'])
    data['parsed'] = {'trade_setup': {'trade_direction': 'Long', 'entry_zone': 'invented provider value'}}

    class NoProvider:

        async def fetch_async(self, *a, **k):
            pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage, refresh_service=NoProvider(), refreshed_data=data))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert 'analysis_completeness' not in saved
    assert 'trade_setup' not in saved['oos_evaluation_inputs']
    _assert_snapshot_integrity(saved)

def test_saved_compact_oos_survives_trimmed_rerun_and_size_governance_keeps_omission_receipts(fixed, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, 'DATA_SNAPSHOT_MAX_BYTES', 50000)
    init_db()
    storage, name, keys, old = report()
    old['analysis_completeness'] = {'status': 'quality_warning', 'quality_warning': True}
    old['oos_evaluation_inputs'] = {'pipeline_id': 'v4', 'trade_setup': {'trade_direction': 'Neutral', 'core_catalyst': 'saved compact contract; original parsed context was trimmed'}}
    old['rerun_context'] = {'analyses': {}, 'pipeline_id': 'v4'}
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    data = deepcopy(old['data'])
    data['recent_catalysts'] = [{'title': f'item {i}', 'summary': 'source text ' * 500} for i in range(20)]

    class NoProvider:

        async def fetch_async(self, *a, **k):
            pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage, refresh_service=NoProvider(), refreshed_data=data))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert saved['oos_evaluation_inputs'] == old['oos_evaluation_inputs']
    assert saved['analysis_completeness'] == old['analysis_completeness']
    assert not saved['rerun_context'].get('parsed', {}).get('trade_setup')
    assert saved['snapshot_truncated'] is True
    assert 'data.recent_catalysts:17' in saved['snapshot_omitted_sections']
    assert len(saved['data']['recent_catalysts']) == 3
    assert saved['snapshot_size_bytes'] <= 50000
    _assert_snapshot_integrity(saved)

def test_explicit_unknown_saved_analysis_metadata_is_not_promoted(fixed, tmp_path):
    init_db()
    storage, name, keys, old = report()
    old['analysis_completeness'] = None
    old['oos_evaluation_inputs'] = {}
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    data = deepcopy(old['data'])
    data['parsed'] = {'trade_setup': {'trade_direction': 'Long'}}

    class NoProvider:

        async def fetch_async(self, *a, **k):
            pytest.fail('unexpected provider')
    asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage, refresh_service=NoProvider(), refreshed_data=data))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert saved['analysis_completeness'] is None and saved['oos_evaluation_inputs'] == {}
    _assert_snapshot_integrity(saved)
