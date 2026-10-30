"""Additional independent V2 probes. Original V1 acceptance file is unchanged."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from itertools import permutations
import json
from pathlib import Path

import pytest
from test_candidate_source_market_identity import unverified_tpex_calendar
from test_cached_institutional_recovery import cached


def bar(day, price=60):
    return {'date': day, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': 0}


@pytest.mark.parametrize('prices', list(permutations([61, 99, 62])))
def test_three_conflicting_variants_remain_blocked_after_reprojection(prices):
    from short_term_market_data import normalize_daily_market_data, build_short_term_market_context
    rows = [bar('2026-10-21')] + [bar('2026-10-22', p) for p in prices] + [bar('2026-10-27')]
    original = deepcopy(rows)
    data = normalize_daily_market_data(rows, ticker='2356.TW', as_of=date(2026, 10, 27))
    assert [r['date'] for r in data['bars']] == ['2026-10-21', '2026-10-27']
    for _ in range(3):
        context = build_short_term_market_context({'ticker': '2356.TW', 'daily_market_data': data}, as_of=date(2026, 10, 27))
        data = context['daily_market_data']
        assert not data['session_integrity']['eligible']
        assert context['technical_indicators']['sample_count'] == 0
    assert rows == original


def test_conflict_stays_visible_when_120_bar_window_is_filled_from_older_rows():
    from short_term_market_data import normalize_daily_market_data
    from market_calendar_store import session_day_status
    days = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(300)
            if session_day_status(date(2026, 1, 1) + timedelta(days=i))['state'] == 'open'][-121:]
    rows = [bar(d) for d in days]
    healthy = normalize_daily_market_data(rows + [bar(days[-1])], ticker='2356.TW', as_of=date(2026, 10, 27))
    assert healthy['sample_count'] == 120 and healthy['session_integrity']['eligible']
    conflict = normalize_daily_market_data(rows + [bar(days[5], 99)], ticker='2356.TW', as_of=date(2026, 10, 27))
    assert conflict['sample_count'] == 120 and not conflict['session_integrity']['eligible']
    assert days[5] not in [b['date'] for b in conflict['bars']]
    assert 'conflicting_duplicate_session' in conflict['session_integrity']['reason_codes']


@pytest.mark.parametrize('stamp, expected_fresh', [
    ('2026-10-05T22:29:59+08:00', True),
    ('2026-10-05T22:30:00+08:00', False),
    ('2026-10-05T22:30:01+08:00', False),
])
def test_institutional_recheck_exact_cutoff_does_not_rewrite_clocks(cached, stamp, expected_fresh):
    from fixtures.institutional_cache import observed
    from fixtures.official_price_cache import observation
    from official_response_evidence import archive_response, read_response
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    from data_freshness import assess_cached_financial_data
    now = datetime.fromisoformat(stamp).timestamp()
    data, _ = cached
    value, _ = observed()
    proof = value['latest_official_observation']['raw_evidence']
    value['latest_official_observation']['raw_evidence'] = archive_response(
        read_response(proof), source_url=proof['source_url'], retrieved_at='2026-10-05T10:00:00+00:00', http_status=200)
    acquired = datetime.fromisoformat('2026-10-05T18:00:00+08:00').timestamp()
    value.update(stale=False, fetched_at_epoch=acquired)
    data['institutional_trading'] = value
    for source, clock in data['source_freshness'].items():
        clock['fetched_at_epoch'] = acquired if source == 'institutional_trading' else now - 10
    data['market_data_fetched_at_epoch'] = data['cache_generated_at_epoch'] = now - 10
    data['daily_market_data']['official_observation'] = observation(retrieved_at=(
        '2026-10-05T10:00:00+00:00' if expected_fresh else '2026-10-05T14:30:00+00:00'))
    original = deepcopy(data)
    fresh, result = assess_session_aligned_cache(data, '6214.TW', assessor=assess_cached_financial_data, now_epoch=now)
    assert fresh is expected_fresh
    assert result['stale_sources'] == ([] if expected_fresh else ['institutional_trading'])
    assert not result['source_freshness']['institutional_trading']['institutional_source_admission']['eligible']
    assert data == original


@pytest.mark.parametrize('stamp, previous', [
    ('2026-10-23T23:00:00+08:00', '2026-10-22'),
    ('2026-07-10T23:00:00+08:00', '2026-07-09'),
])
def test_candidate_nested_source_state_does_not_borrow_twse_closure(tmp_path, stamp, previous, unverified_tpex_calendar):
    from candidate_report_observations import load_candidate_report_observations
    from market_evidence_policy import session_cache_scope
    moment = datetime.fromisoformat(stamp)
    assert session_cache_scope(moment, ticker='1234.TWO')[0] is None
    filename = '1234_TWO_v4_report_job_independent.html'
    snapshot = {'ticker': '1234.TWO', 'pipeline': 'v4', 'data': {'ticker': '1234.TWO',
        'daily_market_data': {'as_of': previous, 'bars': [bar(previous)]},
        'institutional_trading': {'latest_date': previous, 'observation_dates': [previous]}}}
    (tmp_path / filename.replace('.html', '.data.json')).write_text(json.dumps(snapshot))
    result = load_candidate_report_observations([{'ticker': '1234.TWO'}],
        [{'ticker': '1234.TWO', 'latest_report': {'filename': filename}}], str(tmp_path), moment=moment)['1234.TWO']
    assert result['status'] == 'available'
    assert result['expected_completed_session'] is None and not result['latest_source_dates_aligned']
    nested = result['decision_explanation']['source_evidence_state']
    (tmp_path / f'candidate-source-state-{moment:%m%d}.json').write_text(json.dumps({
        'ticker': '1234.TWO', 'evaluation_at': stamp, 'expected_for_tpex': None,
        'outer_expected': result['expected_completed_session'],
        'outer_aligned': result['latest_source_dates_aligned'], 'nested_source_state': nested}, indent=2))
    assert nested['expected_completed_session'] is None, nested
    assert nested['institutional_snapshot_state'] == 'unknown', nested
