"""Source-selection contract: absence, invalidity and failure are distinct."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from institutional_report_status import build_institutional_report_status as project
from test_institutional_report_status import context
from test_institutional_report_identity import latest_context


CASES = [json.loads(p.read_text()) for p in sorted((Path(__file__).parent / 'fixtures/institutional_status_v2_cases').glob('*.json'))]


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['case'])
def test_unmodified_v2_reviewer_counterexamples(case):
    c = deepcopy(case['context']); p = project(c)
    assert p['status'] == case['expected_status']
    assert c == case['context']
    row = c['data']['institutional_trading'].get('latest_official_observation', {})
    if row.get('error_kind'):
        assert p['official_error_kind'] == row['error_kind']
        assert p['official_query_date'] == row['date']
        assert p['official_source_url'] == row['source_url']


SDK_STATES = ('absent', 'none', 'valid', 'empty', 'list', 'bool', 'missing_identity',
              'conflicting_identity', 'failed', 'old', 'missing_clock')


def sdk_record(state, good):
    row = deepcopy(good)
    if state == 'none': return None
    if state == 'empty': return {}
    if state == 'list': return []
    if state == 'bool': return False
    if state == 'missing_identity': row['query'].pop('data_id')
    if state == 'conflicting_identity': row['query']['data_id'] = '2330'
    if state == 'failed': row['error_kind'] = 'SDKTimeout'
    if state == 'old':
        row['query']['end_date'] = '2026-06-15'
        row['retrieved_at'] = '2026-06-15T15:00:00+08:00'
    if state == 'missing_clock': row.pop('retrieved_at')
    return row


@pytest.mark.parametrize('primary_state', SDK_STATES)
@pytest.mark.parametrize('archive_state', SDK_STATES)
def test_primary_archive_cartesian_contract(primary_state, archive_state):
    c = context(); i = c['data']['institutional_trading']; good = i.pop('source_provenance')
    i['official_recovery']['reports'] = []
    if primary_state != 'absent': i['source_provenance'] = sdk_record(primary_state, good)
    if archive_state != 'absent': i['_source_record_archive'] = {'primary_sdk': sdk_record(archive_state, good)}
    invalid = {'empty', 'list', 'bool', 'missing_identity', 'conflicting_identity', 'missing_clock'}
    absent = {'absent', 'none'}
    if primary_state in invalid or archive_state in invalid:
        expected = 'insufficient_evidence'
    elif 'failed' in (primary_state, archive_state):
        expected = 'query_blocked'  # A saved same-session failure is not recovery evidence.
    else:
        selected = archive_state if primary_state in absent else primary_state
        expected = 'insufficient_evidence' if selected in absent else 'query_window_mismatch' if selected == 'old' else 'no_current_rows'
    before = deepcopy(c); result = project(c)
    assert result['status'] == expected
    assert c == before
    if primary_state in absent and archive_state == 'valid':
        assert result['primary_retrieved_at'] == good['retrieved_at']
        assert result['primary_evidence_origin'] == 'archive'


OFFICIAL_STATES = ('absent', 'none', 'valid', 'empty', 'list', 'missing_identity',
                   'failed_status', 'failed_error', 'failed_no_raw', 'old', 'missing_clock')


def official_record(state, row):
    row = deepcopy(row)
    if state == 'none': return None
    if state == 'empty': return {}
    if state == 'list': return []
    if state == 'missing_identity': row.pop('source_url'); row['raw_evidence'].pop('source_url')
    if state == 'failed_status': row['status'] = 'unavailable'
    if state == 'failed_error': row['error_kind'] = 'SourceResponseError'
    if state == 'failed_no_raw': row.update(status='unavailable', error_kind='SourceResponseError', raw_evidence={})
    if state == 'old':
        row['date'] = '2026-06-15'
        row['source_url'] = row['source_url'].replace('20260616', '20260615')
        row['raw_evidence']['source_url'] = row['source_url']
        row['raw_evidence']['retrieved_at'] = '2026-06-15T15:00:00+08:00'
    if state == 'missing_clock': row['raw_evidence'].pop('retrieved_at')
    return row


@pytest.mark.parametrize('current_state', OFFICIAL_STATES)
@pytest.mark.parametrize('latest_state', OFFICIAL_STATES)
def test_current_latest_cartesian_contract(current_state, latest_state):
    c = context(observed='2026-06-16', official='available'); i = c['data']['institutional_trading']; i.pop('source_provenance')
    good_current = i['official_recovery']['reports'][0]
    good_latest = latest_context()['data']['institutional_trading']['latest_official_observation']
    i['official_recovery']['reports'] = [] if current_state in {'absent', 'none'} else [official_record(current_state, good_current)]
    if latest_state != 'absent': i['latest_official_observation'] = official_record(latest_state, good_latest)
    invalid = {'empty', 'list', 'missing_identity', 'missing_clock'}
    if current_state in invalid or latest_state in invalid:
        expected = 'insufficient_evidence'
    elif any(state.startswith('failed') for state in (current_state, latest_state)):
        expected = 'query_blocked'
    elif 'valid' in (current_state, latest_state):
        expected = 'available_provisional'
    else:
        expected = 'insufficient_evidence'
    before = deepcopy(c); result = project(c)
    assert result['status'] == expected
    assert c == before
    if latest_state in {'failed_error', 'failed_no_raw'} and current_state not in invalid:
        assert result['official_error_kind'] == 'SourceResponseError'
        assert result['official_query_date'] == '2026-06-16'


@pytest.mark.parametrize('slot', ['primary', 'archive', 'current', 'latest'])
@pytest.mark.parametrize('state', ['unavailable', 'failed', 'error', 'blocked', 'timeout', 'cooldown'])
def test_explicit_failure_cannot_be_promoted_by_other_success(slot, state):
    c = context(observed='2026-06-16', official='available'); i = c['data']['institutional_trading']
    i['_source_record_archive'] = {'primary_sdk': deepcopy(i['source_provenance'])}
    i['latest_official_observation'] = latest_context()['data']['institutional_trading']['latest_official_observation']
    record = {'primary': i['source_provenance'], 'archive': i['_source_record_archive']['primary_sdk'],
              'current': i['official_recovery']['reports'][0], 'latest': i['latest_official_observation']}[slot]
    record['status'] = state
    assert project(c)['status'] == 'query_blocked'


@pytest.mark.parametrize('slot', ['primary', 'archive', 'current', 'latest'])
@pytest.mark.parametrize('field,value', [('error_kind', False), ('error_kind', []), ('status', False), ('status', {})])
def test_wrong_state_field_type_remains_unknown_despite_other_success(slot, field, value):
    c = context(observed='2026-06-16', official='available'); i = c['data']['institutional_trading']
    i['_source_record_archive'] = {'primary_sdk': deepcopy(i['source_provenance'])}
    i['latest_official_observation'] = latest_context()['data']['institutional_trading']['latest_official_observation']
    record = {'primary': i['source_provenance'], 'archive': i['_source_record_archive']['primary_sdk'],
              'current': i['official_recovery']['reports'][0], 'latest': i['latest_official_observation']}[slot]
    record[field] = value
    assert project(c)['status'] == 'insufficient_evidence'


@pytest.mark.parametrize('archive', [{}, [], False, {'dates': ['2026-06-16']}])
def test_malformed_archive_container_is_not_normalized_into_absence(archive):
    c = context(); c['data']['institutional_trading']['_source_record_archive'] = archive
    p = project(c)
    assert p['status'] == 'insufficient_evidence'
    assert next(r for r in p['source_records'] if r['origin'] == 'archive')['presence'] == 'invalid'


def test_ambiguous_current_records_keep_every_recorded_error():
    c = context(); i = c['data']['institutional_trading']; row = deepcopy(i['official_recovery']['reports'][0])
    row.update(status='unavailable', error_kind='SecondAttemptFailed')
    i['official_recovery']['reports'].append(row)
    p = project(c)
    assert p['status'] == 'insufficient_evidence'
    assert 'current_receipts_ambiguous' in p['limitations']
    assert any(r['error_kind'] == 'SecondAttemptFailed' for r in p['source_records'])


def test_failure_without_bytes_never_borrows_another_slots_receipt_clock():
    c = context(observed='2026-06-16', official='unavailable'); i = c['data']['institutional_trading']
    i['official_recovery']['reports'][0].update(error_kind='CurrentFailed', raw_evidence={})
    i['latest_official_observation'] = latest_context()['data']['institutional_trading']['latest_official_observation']
    p = project(c)
    assert p['status'] == 'query_blocked' and p['official_error_kind'] == 'CurrentFailed'
    assert p['official_evidence_origin'] == 'current' and p['official_retrieved_at'] is None


def test_latest_failure_has_the_same_html_markdown_evidence_and_keeps_gate():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    c = latest_context(); c['evidence_exit_gate'] = {'verdict': 'rejected'}
    row = c['data']['institutional_trading']['latest_official_observation']
    row.update(status='unavailable', error_kind='SourceResponseError')
    before = deepcopy(c); p = project(c)
    assert p['official_evidence_origin'] == 'latest'
    assert p['official_result'] == 'unavailable' and p['official_query_date'] == row['date']
    for text in (build_report_reading_notice_html(c), build_report_reading_notice_markdown(c)):
        assert 'SourceResponseError' in text and 'unavailable' in text and '品質 gate 未通過' in text
    assert c == before


@pytest.mark.parametrize('proof', ['missing', 'old'])
def test_attempt_failure_is_bound_to_its_own_session_not_retained_sdk_bytes(proof):
    c = context(observed='2026-06-16', official='available'); i = c['data']['institutional_trading']
    if proof == 'missing': i.pop('source_provenance')
    else: i['source_provenance']['query']['end_date'] = '2026-06-15'
    c['data']['source_audit'][0]['primary_acquisition']['error_kind'] = 'TimeoutError'
    p = project(c)
    assert p['status'] == 'query_blocked'
    assert p['primary_error_kind'] == 'TimeoutError'


@pytest.mark.parametrize('fault', ['missing', 'invalid', 'conflict'])
def test_attempt_scope_cannot_be_inferred_from_success_or_retained_proof(fault):
    c = context(observed='2026-06-16', official='available'); audit = c['data']['source_audit'][0]
    meta = audit['primary_acquisition']; meta['error_kind'] = 'TimeoutError'
    if fault == 'missing': meta.pop('expected_completed_session')
    elif fault == 'invalid': meta['expected_completed_session'] = 'unknown'
    else: audit['expected_completed_session'] = '2026-06-15'
    p = project(c)
    assert p['status'] == 'insufficient_evidence' and p['primary_error_kind'] == 'TimeoutError'


def test_bound_failed_attempt_without_any_successful_source_is_still_blocked():
    c = context(); i = c['data']['institutional_trading']; i.pop('source_provenance'); i['official_recovery']['reports'] = []
    c['data']['source_audit'][0]['primary_acquisition']['error_kind'] = 'TimeoutError'
    assert project(c)['status'] == 'query_blocked'


def test_known_prior_session_attempt_does_not_replace_current_official_result():
    c = context(observed='2026-06-16', official='available')
    c['data']['source_audit'][0]['primary_acquisition'].update(expected_completed_session='2026-06-15', error_kind='PriorTimeout')
    p = project(c)
    assert p['status'] == 'available_provisional'
    assert p['primary_attempt']['scope'] == 'historical' and p['primary_error_kind'] == 'PriorTimeout'
