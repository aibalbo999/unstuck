"""Saved evidence must describe acquisition, admission and snapshot clocks separately."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


def context(*, day='2026-06-16', observed='2026-06-15', official='valid_empty', cached=False):
    # Complete positive metadata; the original reviewer inputs remain frozen in
    # fixtures/institutional_status_review_counterexamples.json.
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={day.replace('-', '')}&selectType=ALLBUT0999"
    return {
        'ticker': '2855.TW', 'generated_at': f'{day}T17:45:32+08:00',
        'snapshot_refreshed_at': '',
        'data': {
            'analysis_input_cutoff': f'{day}T16:00:00+08:00',
            'daily_market_data': {'as_of': day},
            'market_data_fetched_at': f'{day}T15:57:44+08:00',
            'source_freshness': {'institutional_trading': {'fetch_is_fresh': True, 'stale': True}},
            'source_audit': [{'source': 'institutional_trading', 'primary_acquisition': {
                'expected_completed_session': day, 'cache_hit': False,
            }}],
            'institutional_trading': {
                'latest_date': observed, 'source': 'FinMind',
                'source_provenance': {'status': 'archived', 'retrieved_at': f'{day}T15:57:41+08:00',
                    'query': {'dataset': 'TaiwanStockInstitutionalInvestorsBuySell', 'data_id': '2855',
                              'start_date': '2026-05-01', 'end_date': day}, 'response_row_count': 30},
                'latest_session_admission': {'eligible': False, 'reason': 'latest_institutional_session_missing'},
                'official_recovery': {'status': 'unavailable', 'reports': [{
                    'date': day, 'status': official, 'cache_hit': cached, 'stale': False,
                    'source': 'TWSE T86', 'source_url': url, 'raw_evidence': {'status': 'archived', 'source_url': url,
                        'http_status': 200, 'retrieved_at': f'{day}T15:44:40+08:00'},
                }]},
            },
        },
    }


def project(value):
    from institutional_report_status import build_institutional_report_status
    return build_institutional_report_status(value)


def test_successful_empty_is_bounded_to_receipt_not_official_publication():
    p = project(context())
    assert p['query_status'] == 'no_current_rows'
    assert p['status'] == 'no_current_rows'
    assert p['official_publication_status'] == 'unknown'
    assert '不能證明官方尚未發布' in p['summary']
    assert p['snapshot_status'] == 'saved_unrefreshed'
    assert p['price_date'] == '2026-06-16' and p['institutional_date'] == '2026-06-15'
    assert p['primary_retrieved_at'] == '2026-06-16T15:57:41+08:00'


def test_2855_shared_cooldown_does_not_reuse_old_empty_as_success():
    c = context(official='unavailable', cached=True)
    row = c['data']['institutional_trading']['official_recovery']['reports'][0]
    row.update(error_kind='SourceResponseError', stale=True)
    p = project(c)
    assert p['status'] == p['query_status'] == 'query_blocked'
    assert p['official_error_kind'] == 'SourceResponseError'
    assert p['official_retrieved_at'] == '2026-06-16T15:44:40+08:00'
    assert '舊回應' in p['summary']
    assert '尚未發布' not in p['label']


@pytest.mark.parametrize('kind', ['timeout', 'cooldown', 'single_flight_busy', 'ProviderCircuitOpenError'])
def test_failed_attempt_cannot_become_success_from_retained_bytes(kind):
    c = context()
    c['data']['institutional_trading']['official_recovery']['reports'][0]['error_kind'] = kind
    assert project(c)['query_status'] == 'query_blocked'


def test_same_day_rows_before_cutoff_are_available_but_not_admitted():
    c = context(observed='2026-06-16', official='available')
    c['data']['institutional_trading']['latest_session_admission']['reason'] = 'official_observation_is_provisional'
    p = project(c)
    assert p['query_status'] == 'current_rows'
    assert p['status'] == 'available_provisional'
    assert p['recorded_admission_eligible'] is False
    assert '內部' in p['policy_note'] and '官方發布 SLA' in p['policy_note']
    assert p['cache_status'] != 'expired'  # Generic stale includes admission restrictions.


def test_after_cutoff_report_save_never_upgrades_earlier_receipt():
    c = context(observed='2026-06-16', official='available')
    c['generated_at'] = '2026-06-17T01:00:00+08:00'
    assert project(c)['status'] == 'available_provisional'
    assert project(c)['report_saved_at'] == c['generated_at']


def test_historical_query_bound_is_not_publication_wait():
    c = context()
    inst = c['data']['institutional_trading']
    inst['source_provenance']['query']['end_date'] = '2026-06-12'
    inst['official_recovery']['reports'][0]['date'] = '2026-06-12'
    c['data']['source_audit'][0]['primary_acquisition']['expected_completed_session'] = '2026-06-12'
    p = project(c)
    assert p['status'] == 'query_window_mismatch'
    assert p['query_end_date'] == '2026-06-12'
    assert '行情交易日' in p['summary']


def test_current_official_query_is_not_hidden_by_old_primary_query_bound():
    c = context()
    c['data']['institutional_trading']['source_provenance']['query']['end_date'] = '2026-06-12'
    p = project(c)
    assert p['query_status'] == 'no_current_rows'
    assert 'primary_query_window_mismatch' in p['limitations']


def test_empty_official_receipt_does_not_date_a_later_primary_current_row():
    c = context(observed='2026-06-16')
    c['data']['analysis_input_cutoff'] = '2026-06-16T23:00:00+08:00'
    c['generated_at'] = '2026-06-16T23:05:00+08:00'
    inst = c['data']['institutional_trading']
    inst['source_provenance']['retrieved_at'] = '2026-06-16T22:35:00+08:00'
    inst['latest_session_admission']['reason'] = 'latest_official_raw_evidence_missing'
    assert project(c)['status'] == 'available_requires_verification'


@pytest.mark.parametrize('start,end', [('2026-06-17', '2026-06-18'), ('2026-06-18', '2026-06-17')])
def test_primary_query_must_contain_price_session_at_both_bounds(start, end):
    c = context()
    inst = c['data']['institutional_trading']
    inst['official_recovery']['reports'] = []
    inst['source_provenance']['query'].update(start_date=start, end_date=end)
    assert project(c)['query_status'] == 'query_window_mismatch'


def test_missing_query_start_cannot_prove_successful_target_query():
    c = context()
    inst = c['data']['institutional_trading']
    inst['official_recovery']['reports'] = []
    inst['source_provenance']['query'].pop('start_date')
    assert project(c)['query_status'] == 'unknown'


def test_cached_empty_is_not_a_new_successful_request():
    p = project(context(cached=True))
    assert p['query_status'] == 'cached_no_current_rows'
    assert '快取' in p['summary']


def test_expired_cache_is_distinct_from_internal_admission_stale():
    c = context(cached=True)
    c['data']['source_freshness']['institutional_trading'].update(fetch_is_fresh=False)
    p = project(c)
    assert p['cache_status'] == 'expired'
    assert p['status'] == 'cache_expired'
    assert p['query_status'] == 'cached_no_current_rows'


def test_weekend_or_holiday_uses_saved_price_session_without_weekday_guessing():
    c = context(day='2026-06-12', observed='2026-06-12', official='available')
    c['generated_at'] = '2026-06-14T12:00:00+08:00'
    p = project(c)
    assert p['price_date'] == p['institutional_date'] == '2026-06-12'
    assert p['query_status'] == 'current_rows'


def test_tpex_identity_is_displayed_without_borrowing_twse_calendar():
    c = context()
    c['ticker'] = '6543.TWO'
    c['data']['institutional_trading']['official_recovery']['reports'][0]['source'] = 'TPEx dailyTrade'
    assert project(c)['market'] == 'TPEX'
    c['ticker'] = '6543'
    assert project(c)['market'] == 'unknown'
    assert project(c)['status'] == 'insufficient_evidence'


def test_wrong_exchange_receipt_cannot_establish_successful_current_query():
    c = context()
    c['ticker'] = '6543.TWO'  # Retained TWSE receipt belongs to a different exchange.
    p = project(c)
    assert p['status'] == 'insufficient_evidence'
    assert p['query_status'] == 'unknown'
    assert 'official_market_mismatch' in p['limitations']


def test_legacy_error_without_attempt_session_remains_unknown_but_is_retained():
    c = context()
    c['data']['source_audit'][0].pop('primary_acquisition')
    c['data']['source_audit'][0]['error_kind'] = 'TimeoutError'
    c['data']['institutional_trading']['official_recovery']['reports'] = []
    p = project(c)
    assert p['query_status'] == 'unknown'
    assert p['primary_error_kind'] == 'TimeoutError'
    assert 'primary_attempt_session_missing' in p['limitations']


def test_future_receipt_is_not_used_to_explain_original_availability():
    c = context()
    c['data']['institutional_trading']['official_recovery']['reports'][0]['raw_evidence']['retrieved_at'] = '2026-06-16T18:00:00+08:00'
    p = project(c)
    assert p['status'] == 'evidence_time_conflict'
    assert 'receipt_after_snapshot_cutoff' in p['limitations']


def test_source_refresh_is_distinct_from_saved_original_conclusion():
    c = context()
    c.update(snapshot_refreshed_at='2026-06-17T12:00:00+08:00', refreshed_without_analysis_rerun=True,
             conclusion_generated_at='2026-06-16T17:45:32+08:00')
    p = project(c)
    assert p['snapshot_status'] == 'sources_refreshed_without_analysis'
    assert p['conclusion_generated_at'] != p['snapshot_refreshed_at']


def test_missing_primary_receipt_does_not_promote_aggregate_timestamp_to_actual_fetch():
    c = context()
    inst = c['data']['institutional_trading']
    inst.pop('source_provenance')
    inst['fetched_at_epoch'] = 1781582400
    assert project(c)['primary_retrieved_at'] is None


def test_undated_empty_does_not_prove_successful_target_query():
    c = context()
    inst = c['data']['institutional_trading']
    inst.pop('source_provenance')
    inst['official_recovery']['reports'][0]['raw_evidence'] = {}
    assert project(c)['query_status'] == 'unknown'


def test_projection_is_pure_and_html_markdown_share_exact_labels():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    from reporting.reading_notice_values import build_report_reading_notice_values
    c = context(); original = deepcopy(c)
    p = project(c)
    values = build_report_reading_notice_values(c)
    assert values['institutional_status'] == p
    assert p['label'] in build_report_reading_notice_html(c)
    assert p['label'] in build_report_reading_notice_markdown(c)
    assert '2026-06-16 15:57:41 +08:00' in build_report_reading_notice_html(c)
    assert '2026-06-16 17:45:32 +08:00' in build_report_reading_notice_markdown(c)
    assert c == original


@pytest.mark.parametrize('value', [None, {}, {'data': None}, {'data': {'institutional_trading': []}}])
def test_absent_data_does_not_invent_a_state(value):
    assert project(value) == {}


@pytest.mark.parametrize('kind', ['view', 'html', 'md'])
def test_existing_report_view_and_download_project_notice_without_writing_artifacts(kind):
    import json
    from data_trust import data_snapshot_filename_for_report
    from report_history_service import get_report_file, download_report_file
    from storage.report_storage import InMemoryStorage
    storage = InMemoryStorage()
    filename = '2855_TW_v4_report_20260616_174532.html'
    c = context(official='unavailable', cached=True)
    c['data']['institutional_trading']['official_recovery']['reports'][0]['error_kind'] = 'SourceResponseError'
    contents = {
        filename: ('text/html', b'<html><body><p>original analysis</p></body></html>'),
        filename[:-5] + '.md': ('text/markdown', b'# original analysis'),
        data_snapshot_filename_for_report(filename): ('application/json', json.dumps(c).encode()),
    }
    for key, (mime, body) in contents.items():
        storage.save_report(key, body, content_type=mime)

    class Repository:
        def query(self, query):
            assert query.sync_metadata is False
            return ([{'filename': filename, 'evidence_exit_gate': {'verdict': 'caution'},
                      'report_conformance': {'status': 'warning'},
                      'content_credibility': {'status': 'warning'}}], 1)

    args = {'storage': storage, 'repository': Repository()}
    response = get_report_file(filename, '/absent', **args) if kind == 'view' else download_report_file(filename, '/absent', kind, **args)
    body = response.body.decode()
    assert project(c)['label'] in body
    assert '品質 gate 有警示' in body
    assert 'original analysis' in body
    for key, (_, original) in contents.items():
        assert storage.get_report(key).content == original


def test_supplemental_diagnosis_does_not_modify_quality_gate_verdicts():
    from reporting.reading_notice_values import build_report_reading_notice_values
    c = context()
    c.update(evidence_exit_gate={'verdict': 'rejected'}, content_credibility={'status': 'blocked'},
             report_conformance={'status': 'blocked'})
    before = deepcopy(c)
    assert build_report_reading_notice_values(c)['state'] == 'blocked'
    assert c == before
