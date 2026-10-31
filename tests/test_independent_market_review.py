"""Independent acceptance probes for frozen commit 4adf13d; no production writes."""
from copy import deepcopy
from datetime import date, datetime
from collections import Counter
from pathlib import Path
import json

import pytest
from test_cached_institutional_recovery import cached
from test_candidate_source_market_identity import unverified_tpex_calendar


def bar(day, close=60, volume=0):
    return dict(date=day, open=close, high=close, low=close, close=close, volume=volume)


def daily(days, ticker='2356.TW'):
    return dict(ticker=ticker, as_of=days[-1], source='independent fixture',
                bars=[bar(day) for day in days])


@pytest.mark.parametrize('day', ['2026-07-10', '2026-10-23', '2026-10-26'])
def test_official_twse_closed_dates(day):
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(daily([day]))
    assert result['status'] == 'invalid'
    assert result['closed_dates'] == [day]


def test_open_zero_volume_and_missing_day_are_distinct():
    from market_session_admission import assess_daily_session_integrity
    assert assess_daily_session_integrity(daily(['2026-10-22', '2026-10-27']))['eligible']
    result = assess_daily_session_integrity(daily(['2026-10-21', '2026-10-27']))
    assert not result['eligible'] and result['missing_expected_dates'] == ['2026-10-22']


@pytest.mark.parametrize('ticker', ['1234.TWO', '1234', ''])
def test_unproven_market_does_not_borrow_emergency_evidence(ticker, unverified_tpex_calendar):
    from market_session_admission import assess_daily_session_integrity
    result = assess_daily_session_integrity(daily(['2026-10-23'], ticker))
    assert not result['eligible'] and result['status'] == 'unverifiable'


def test_conflicting_duplicate_must_not_become_admitted_after_normalization():
    from short_term_market_data import normalize_daily_market_data
    from market_session_admission import assess_daily_session_integrity
    rows = [bar('2026-10-21', 60), bar('2026-10-22', 61), bar('2026-10-22', 99), bar('2026-10-27', 62)]
    original = deepcopy(rows)
    assert not assess_daily_session_integrity(dict(ticker='2356.TW', as_of='2026-10-27', bars=rows))['eligible']
    result = normalize_daily_market_data(rows, ticker='2356.TW', as_of=date(2026, 10, 27))
    assert rows == original
    assert not result['session_integrity']['eligible'], result


def test_invalid_quarantine_must_survive_context_projection():
    from short_term_market_data import build_short_term_market_context
    from market_session_admission import assess_daily_session_integrity
    value = daily(['2026-10-27'])
    value['quarantined_session_rows'] = [{'date': {}, 'state': 'unknown'}]
    assert not assess_daily_session_integrity(value)['eligible']
    result = build_short_term_market_context({'ticker': '2356.TW', 'daily_market_data': value}, as_of=date(2026, 10, 27))
    assert not result['daily_market_data']['session_integrity']['eligible'], result


def test_tpex_readiness_must_use_tpex_calendar_scope(unverified_tpex_calendar):
    from two_week_market_eligibility import completed_session
    from reporting.content_credibility_observations import evaluate_observation_credibility
    moment = datetime.fromisoformat('2026-10-23T18:00:00+08:00')
    assert completed_session(moment, ticker='1234.TWO') is None
    data = {'ticker': '1234.TWO', 'current_price': 60,
            'daily_market_data': daily(['2026-10-22'], '1234.TWO'),
            'institutional_trading': {'observation_dates': ['2026-10-22']}}
    result = evaluate_observation_credibility({'candidate_evaluation_at': moment.isoformat()}, {}, data, 'v4')
    readiness = result['checks'][0]['details']
    assert not readiness['latest_source_dates_aligned'], readiness


def test_same_input_arithmetic_is_not_external_verification():
    from technical_reasoning import sma_reasoning_checks
    from short_term_technical_indicators import calculate_technical_indicators
    value = daily(['2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-27'])
    value['price_adjustment_basis'] = 'synthetic fixed basis'
    value['bars'] = [bar(row['date'], 60+i) for i,row in enumerate(value['bars'])]
    data = {'ticker': '2356.TW', 'daily_market_data': value,
            'technical_indicators': calculate_technical_indicators(value)}
    check = sma_reasoning_checks('收盤價高於5日線。', data)[0]
    assert check['arithmetic_status'] == 'verified'
    assert check['verification_scope'] == 'saved_window_arithmetic'
    assert not check['independent_primary_source_verified']
    assert not check['historical_point_in_time_verified']


def test_post_cutoff_workflow_must_recheck_provisional_institutional_receipt(cached):
    from test_cached_institutional_recovery import run
    from fixtures.institutional_cache import observed, NOW
    from official_response_evidence import archive_response, read_response
    from report_source_admission import institutional_admission
    from data_freshness import assess_cached_financial_data
    data, _ = cached
    value, audit = observed()
    proof = value['latest_official_observation']['raw_evidence']
    value['latest_official_observation']['raw_evidence'] = archive_response(
        read_response(proof), source_url=proof['source_url'],
        retrieved_at='2026-10-05T10:00:00+00:00', http_status=200)
    value['latest_session_admission'] = institutional_admission(value, '2026-10-05')
    assert not value['latest_session_admission']['eligible']
    original_acquired = datetime.fromisoformat('2026-10-05T18:00:00+08:00').timestamp()
    value['fetched_at_epoch'] = original_acquired
    data['institutional_trading'] = value
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': original_acquired, 'stale': False}
    assert assess_cached_financial_data(data, '6214.TW')[0]
    result, calls = run(cached, *observed())
    assert calls, 'Outer workflow returns a cache hit without reacquiring a provisional institutional original'


def test_selected_fcf_missing_component_or_period_cannot_clear_warning():
    from test_official_financial_projection import projected
    from reporting.content_credibility_fcf_scope import fcf_quality_scope
    baseline = projected()
    scope = fcf_quality_scope(baseline)
    assert scope['selected_field']['period_status'] == 'verified'
    assert scope['preserved_quote']['period_status'] == 'unverified'
    for change in ['period', 'intangible_capex', 'annual_only']:
        data = deepcopy(baseline)
        if change == 'period':
            data['official_financial_projection']['facts']['period_start'] = '2026-01-01'
        elif change == 'intangible_capex':
            data['official_financial_projection']['facts']['cashflows']['ttm'].pop('intangible_purchase')
        else:
            data.pop('official_financial_projection')
            data['years'] = ['2025']
            data['fcf_history'] = [data['free_cash_flow_raw'] / 1e9]
        assert fcf_quality_scope(data)['selected_field']['period_status'] == 'unverified'


def test_closed_checkpoint_stops_before_runner(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    import report_rerun_service as service
    data = {'ticker': '2356.TW', 'daily_market_data': daily(['2026-10-23'])}
    snapshot = {'ticker': '2356.TW', 'data': data}
    async def checkpoint(**kwargs):
        return {'thread_id': 'synthetic-polluted'}, deepcopy(data)
    class Runner:
        async def run_async(self, *args, **kwargs):
            pytest.fail('Polluted checkpoint reached model runner')
    monkeypatch.setattr(service, 'full_rerun_checkpoint', checkpoint)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(service._run_full_pipeline_rerun(snapshot=snapshot, output_dir='unused',
            pipeline_runner=Runner(), report_renderer=None, source_filename='2356_TW_v4_report_job_example.html',
            pipeline_id='v4', scope='full_report'))
    assert caught.value.status_code == 409


def test_classification_never_changes_quality_status_or_counts():
    from report_quality_reason_classification import explain_quality_population
    rows = [{'report_date': '2026-10-27', 'pipeline_id': 'v4',
             'content_credibility': {'status': 'blocked', 'blocking_issues': [
                 {'id': 'v4_trade_reason_source_missing'}, {'id': 'v4_market_session_integrity_invalid'}],
                 'warnings': [{'id': 'v4_raw_fcf_period_unverified'}]}},
            {'report_date': '2026-10-22', 'pipeline_id': 'v4',
             'content_credibility': {'status': 'warning', 'warnings': [{'id': 'v4_raw_fcf_period_unverified'}]}}]
    before = deepcopy(rows)
    result = explain_quality_population(rows, selection_basis='latest_per_ticker_pipeline',
        now=datetime.fromisoformat('2026-10-27T23:00:00+08:00'))
    assert rows == before and result['denominator']['count'] == 2
    assert result['reason_classification']['counts_may_overlap']
    assert result['content_credibility_warning_counts']['v4_raw_fcf_period_unverified'] == 2
    assert 'passed' not in result


def test_preview_21_reports_read_only_and_hash_bound():
    from report_rebuild_preview import read_saved_bundle, build_rebuild_preview
    root = Path(__file__).resolve().parents[1]
    saved = json.loads((root/'docs/rebuild-preview-20261027.json').read_text())
    output = '/Volumes/X10 Pro Mac/stock-agent/backend/output'
    results = []
    for plan in saved['reports']:
        snapshot, before = read_saved_bundle(output, plan['filename'])
        assert before == plan['artifact_sha256']
        rebuilt = build_rebuild_preview(snapshot, filename=plan['filename'], artifact_hashes=before,
                                        evaluated_at=datetime.fromisoformat(plan['evaluated_at']))
        _, after = read_saved_bundle(output, plan['filename'])
        assert before == after
        assert rebuilt == plan
        results.append({'filename': plan['filename'], 'artifact_sha256': before,
                        'after_as_of': rebuilt['comparison']['after_as_of']})
    counts = Counter(p['after_as_of'] for p in results)
    assert len(results) == 21 and counts == {'2026-10-22': 12, '2026-10-27': 9}
    (root.parent/'evidence/preview-readback-independent.json').write_text(json.dumps({
        'report_count': len(results), 'artifact_count': len(results)*3,
        'original_hashes_unchanged': True, 'replayed_plan_equal': True,
        'after_as_of_counts': dict(counts), 'reports': results}, indent=2))
