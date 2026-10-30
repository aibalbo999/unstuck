"""Fresh acquisition clocks must not hide an available completed session."""
from copy import deepcopy
from datetime import datetime
import pytest

from data_freshness import assess_cached_financial_data
from test_cached_institutional_recovery import cached, run
from fixtures.institutional_cache import NOW, observed


def recent_previous_session(data):
    data['institutional_trading'].update(latest_date='2026-10-02', stale=False)
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': NOW, 'stale': False}
    assert assess_cached_financial_data(data, '6214.TW')[0]


def test_fresh_acquisition_behind_completed_session_recovers_only_institutions(cached):
    data, writes = cached
    recent_previous_session(data)
    before = deepcopy(data)
    value, audit = observed()
    result, calls = run(cached, value, audit)
    assert len(calls) == 1
    assert calls[0].options.force_refresh is False
    assert result.data['institutional_trading'] == value
    assert writes and writes[-1]['institutional_trading'] == value
    assert result.data['source_freshness']['market_data']['fetched_at_epoch'] == NOW
    assert data == before


def test_session_gap_failure_preserves_old_values_clocks_and_cache(cached):
    data, writes = cached
    recent_previous_session(data)
    value, audit = observed()
    audit.update(status='error', error_kind='timeout', record_count=0, fetched_at_epoch=None)
    result, calls = run(cached, None, audit)
    assert len(calls) == 1
    assert result.data['institutional_trading'] == data['institutional_trading']
    assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == NOW
    assert result.data['source_freshness']['institutional_trading']['stale'] is True
    assert not writes


def test_current_completed_session_keeps_normal_cache_hit(cached):
    data, writes = cached
    data['institutional_trading'] = observed()[0]
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': NOW, 'stale': False}
    result, calls = run(cached, *observed())
    assert not calls and not writes
    assert result.data['institutional_trading'] == data['institutional_trading']


def test_before_maturity_boundary_can_request_publication_without_promoting_it(cached):
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    data, _ = cached
    recent_previous_session(data)
    fresh, assessment = assess_session_aligned_cache(
        data, '6214.TW', assessor=assess_cached_financial_data,
        now_epoch=datetime.fromisoformat('2026-10-05T22:29:59+08:00').timestamp())
    assert not fresh and assessment['stale_sources'] == ['institutional_trading']
    institutional = assessment['source_freshness']['institutional_trading']
    assert institutional['expected_session'] == '2026-10-05'
    assert institutional['acquisition_scope']['mature_evidence_session'] == '2026-10-02'
    assert institutional['acquisition_scope']['acquisition_phase'] == 'provisional'


@pytest.mark.parametrize('change', ['unknown_calendar', 'wrong_ticker', 'future_session', 'invalid_date'])
def test_alignment_does_not_invent_or_rewrite_dates(cached, monkeypatch, change):
    from data_fetch import cache_session_alignment as alignment
    data, _ = cached
    recent_previous_session(data)
    if change == 'unknown_calendar':
        monkeypatch.setattr(alignment, 'acquisition_session_scope', lambda moment, **kw: {
            'latest_completed_session': None, 'mature_evidence_session': None,
            'acquisition_phase': 'unknown'})
    elif change == 'wrong_ticker':
        data['ticker'] = '2330.TW'
    else:
        data['institutional_trading']['latest_date'] = '2026-10-06' if change == 'future_session' else 'bad'
    before = deepcopy(data)
    actual = alignment.assess_session_aligned_cache(data, '6214.TW', assessor=assess_cached_financial_data, now_epoch=NOW)
    assert actual[0] is False
    source = 'market_data' if change == 'wrong_ticker' else 'institutional_trading'
    assert source in actual[1]['stale_sources']
    assert actual[1]['source_freshness'][source]['fetched_at_epoch'] == NOW
    assert data == before
