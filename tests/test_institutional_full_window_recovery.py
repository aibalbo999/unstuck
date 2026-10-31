"""A real holiday-window gap must be fetched, never assumed or filled as zero."""
from copy import deepcopy
from datetime import date, datetime, timezone
import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / 'fixtures/source_acquisition/institutional_6152_full30_20261012'
MANIFEST = json.loads((FIXTURES / 'manifest.json').read_text())
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def clock_and_calendar(monkeypatch):
    import cache_store
    import data_fetch.market_sources.taiwan as taiwan
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr('time.time', lambda: NOW)
    monkeypatch.setattr('data_freshness_market.market_calendar', lambda *a, **k: {
        'coverage_status': 'available', 'holidays': {date.fromisoformat(v) for v in MANIFEST['holidays_in_bound_window']}})
    yield
    cache_store.reset_cache_store_for_tests()


def primary29():
    return json.loads((FIXTURES / 'actual_primary29.json').read_text())


def install_original_reports(monkeypatch, primary, *, absent_missing=False, fail_missing=False, retrieved_at=None):
    import official_institutional_source as source
    from official_response_evidence import archive_response
    calls = []
    def fetch(market, day, timeout, **kwargs):
        calls.append(day)
        if day == '2026-08-27':
            if fail_missing: raise TimeoutError('official window gap unavailable')
            raw = gzip.decompress((FIXTURES / 'missing_Aug27.json.gz').read_bytes())
            value = source._parse_report(json.loads(raw), market, day)
            if absent_missing: value['rows'].pop('6152')
        elif day == '2026-10-12':
            raw = gzip.decompress((FIXTURES / 'latest_Oct12.json.gz').read_bytes())
            value = source._parse_report(json.loads(raw), market, day)
        else:
            categories = {r['category']: r['net_buy_shares'] for r in primary['daily_category_observations'] if r['date'] == day}
            return {'date': day, 'rows': {'6152': {'company_name': '百一', **categories}}, 'market': market, 'report_status': 'available'}
        value['raw_evidence'] = archive_response(raw, source_url=source._url(market, day),
            retrieved_at=retrieved_at or datetime.fromtimestamp(NOW, timezone.utc).isoformat(), http_status=200)
        value['source'] = source.TWSE_SOURCE
        return value
    monkeypatch.setattr(source, '_fetch_report', fetch)
    return calls


def test_public_finmind_query_covers_all_thirty_completed_exchange_sessions(monkeypatch):
    import data_fetch.market_sources.taiwan as taiwan
    calls = []
    all_dates = MANIFEST['expected30']
    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame([{'stock_id': '6152', 'date': day, 'name': category, 'buy': 1000, 'sell': 0}
                                 for day in all_dates if day >= kwargs['start_date']
                                 for category in ['Foreign_Investor', 'Investment_Trust', 'Dealer_self']])
    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    value = taiwan.fetch_institutional_trading_trend('6152.TW')
    assert len(value['observation_dates']) == 30
    assert value['observation_dates'][0] == '2026-08-27'
    assert value['window_coverage_status'] == 'complete'
    assert calls == [{'stock_id': '6152', 'start_date': '2026-08-27', 'end_date': '2026-10-12'}]


def test_official_recovery_prioritizes_missing_thirtieth_day_with_same_five_report_cap(monkeypatch):
    import official_institutional_source as source
    original = primary29(); calls = []
    def fetch(market, day, timeout, **kwargs):
        calls.append(day)
        if day == '2026-08-27':
            return source._parse_report(json.loads(gzip.decompress((FIXTURES / 'missing_Aug27.json.gz').read_bytes())), market, day)
        categories = {row['category']: row['net_buy_shares'] for row in original['daily_category_observations'] if row['date'] == day}
        return {'date': day, 'rows': {'6152': {'company_name': '百一', **categories}}, 'market': market, 'report_status': 'available'}
    monkeypatch.setattr(source, '_fetch_report', fetch)
    value, audit = source.recover_institutional_observations('6152.TW', original, now_epoch=NOW, limit=30)
    assert value['observed_date_count'] == 30
    assert value['window_coverage_status'] == 'complete'
    assert calls[0] == '2026-10-12' and calls[1] == '2026-08-27'
    assert len(calls) <= source.MAX_REPORTS == 5
    assert audit['added_observation_count'] == 3
    restored = [r for r in value['daily_category_observations'] if r['date'] == '2026-08-27']
    assert {r['category']: r['net_buy_shares'] for r in restored} == {
        'foreign': 122271, 'investment_trust': 0, 'dealer': -8000}
    assert primary29() == original


@pytest.mark.parametrize('missing_kind', ['absent', 'error'])
def test_no_missing_row_or_failed_request_can_become_a_zero_observation(monkeypatch, missing_kind):
    import official_institutional_source as source
    primary = primary29(); before = deepcopy(primary)
    calls = install_original_reports(monkeypatch, primary, absent_missing=missing_kind == 'absent', fail_missing=missing_kind == 'error')
    value, audit = source.recover_institutional_observations('6152.TW', primary, now_epoch=NOW, limit=30)
    assert value['observed_date_count'] == 29 and value['window_coverage_status'] == 'missing_sessions'
    assert not any(r['date'] == '2026-08-27' for r in value['daily_category_observations'])
    assert audit['added_observation_count'] == 0 and len(calls) <= 5
    assert primary == before


def test_full_thirty_day_recovery_does_not_promote_provisional_latest_official_data(monkeypatch):
    import official_institutional_source as source
    from report_source_admission import institutional_admission
    primary = primary29(); install_original_reports(
        monkeypatch, primary, retrieved_at='2026-10-12T13:30:00+00:00')
    value, audit = source.recover_institutional_observations('6152.TW', primary, now_epoch=NOW, limit=30)
    assert value['observed_date_count'] == 30 and value['window_coverage_status'] == 'complete'
    admission = institutional_admission(value, '2026-10-12')
    assert admission['eligible'] is False and admission['reason'] == 'official_observation_is_provisional'
    # The fetch was requested after the conservative cutoff, but the archived
    # response timestamp is pre-cutoff; admission still rejects its raw proof.
    assert value['latest_official_observation']['acquisition_phase'] == 'post_cutoff'
    assert audit['coverage_scope'] == 'latest session and selected gaps; not full official window verification'


def test_primary_sdk_receipt_is_retained_separately_and_dropped_at_prompt_boundary(monkeypatch):
    import official_institutional_source as source
    from prompt_evidence import prompt_evidence_copy
    primary = primary29()
    primary['source_provenance'] = {'evidence_kind': 'sdk_dataframe_json_not_raw_http',
                                    'http_status': None, 'raw_response_path': '/private/only-our-new-provenance'}
    before = deepcopy(primary); install_original_reports(monkeypatch, primary)
    value, audit = source.recover_institutional_observations('6152.TW', primary, now_epoch=NOW, limit=30)
    archive = value['_source_record_archive']
    assert archive['primary_sdk'] == primary['source_provenance'] and len(archive['primary_observation_dates']) == 29
    projected = prompt_evidence_copy({'institutional_trading': value})
    assert '/private/only-our-new-provenance' not in json.dumps(projected)
    archive['primary_sdk']['http_status'] = 200
    assert primary == before and primary['source_provenance']['http_status'] is None


def test_complete_primary_retains_latest_five_plan_and_no_extra_old_day(monkeypatch):
    import official_institutional_source as source
    primary = primary29(); old = source._parse_report(json.loads(gzip.decompress((FIXTURES / 'missing_Aug27.json.gz').read_bytes())), 'TWSE', '2026-08-27')['rows']['6152']
    primary['daily_category_observations'] += [{'date': '2026-08-27', 'category': c, 'net_buy_shares': old[c], 'source': 'TWSE T86', 'unit': 'shares'} for c in ('foreign', 'investment_trust', 'dealer')]
    calls = install_original_reports(monkeypatch, primary)
    value, audit = source.recover_institutional_observations('6152.TW', primary, now_epoch=NOW, limit=30)
    assert calls == ['2026-10-12', '2026-10-08', '2026-10-07', '2026-10-06', '2026-10-05']
    assert audit['missing_expected_dates'] == [] and audit['added_observation_count'] == 0


def test_unknown_calendar_does_not_invent_earlier_sdk_window_or_make_official_requests(monkeypatch):
    import data_fetch.market_sources.taiwan as taiwan
    import official_institutional_source as source
    monkeypatch.setattr('data_freshness_market.market_calendar', lambda *a, **k: {'coverage_status': 'unavailable', 'holidays': set()})
    calls = []
    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            calls.append(kwargs); return pd.DataFrame()
    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    assert taiwan.fetch_institutional_trading_trend('6152.TW') == {}
    assert calls == [], 'Unknown calendar must not manufacture a provisional query bound'
    official_calls = install_original_reports(monkeypatch, primary29())
    value, audit = source.recover_institutional_observations('6152.TW', primary29(), now_epoch=NOW, limit=30)
    assert official_calls == [] and audit['status'] == 'calendar_unknown'


def test_latest_source_conflict_keeps_primary_numbers_and_conflict_warning(monkeypatch):
    import official_institutional_source as source
    primary = primary29(); original_latest = next(r for r in primary['daily_category_observations'] if r['date'] == '2026-10-12' and r['category'] == 'foreign')
    original_latest['net_buy_shares'] += 100; changed = original_latest['net_buy_shares']
    install_original_reports(monkeypatch, primary)
    value, audit = source.recover_institutional_observations('6152.TW', primary, now_epoch=NOW, limit=30)
    saved = next(r for r in value['daily_category_observations'] if r['date'] == '2026-10-12' and r['category'] == 'foreign')
    assert saved['net_buy_shares'] == changed and audit['conflicts'][0]['selected'] == 'primary'
    assert audit['conflicts'][0]['official']['net_buy_shares'] == -3918687
