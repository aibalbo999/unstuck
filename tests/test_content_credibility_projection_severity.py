"""Re-audit cannot erase unknown historical severity or current findings."""
import copy

import pytest

from reporting.content_credibility_projection import merge_content_credibility_results


def approved():
    return {'status': 'passed', 'checks': [
        {'id': 'confidence_evidence_alignment', 'status': 'passed',
         'details': {'evidence_verdict': 'approved'}}]}


@pytest.mark.parametrize('status', ['warning', 'blocked', 'failed', 'rejected'])
def test_unexplained_historical_severity_survives_unrelated_passing_check(status):
    old = {'status': status, 'warnings': [], 'blocking_issues': []}
    assert merge_content_credibility_results(old, approved())['status'] == status


def test_warning_does_not_explain_a_historical_block():
    old = {'status': 'blocked', 'warnings': [{'id': 'non_approved_evidence_gate'}]}
    result = merge_content_credibility_results(old, approved())
    assert result['status'] == 'blocked'
    assert result['warnings'] == []


@pytest.mark.parametrize('status', ['warning', 'blocked'])
def test_unrelated_check_only_severity_remains_visible(status):
    old = {'status': status, 'warnings': [{'id': 'non_approved_evidence_gate'}],
           'checks': [{'id': 'historical_unknown_check', 'status': status}]}
    result = merge_content_credibility_results(old, approved())
    assert result['status'] == status
    assert any(c['id'] == 'historical_unknown_check' for c in result['checks'])


def test_current_issue_cannot_be_erased_by_a_contradictory_passed_check():
    current = approved()
    current.update(status='warning', warnings=[{'id': 'non_approved_evidence_gate', 'message': 'still failing'}])
    result = merge_content_credibility_results({'status': 'warning'}, current)
    assert result['warnings'] == current['warnings']
    assert result['status'] == 'warning'


def test_exact_resolved_warning_or_block_can_improve_without_mutation():
    for field, status, issue in [('warnings', 'warning', 'non_approved_evidence_gate'),
                                 ('blocking_issues', 'blocked', 'high_confidence_rejected_evidence')]:
        old = {'status': status, field: [{'id': issue}]}
        original = copy.deepcopy(old)
        result = merge_content_credibility_results(old, approved())
        assert result['status'] == 'passed'
        assert old == original


def test_recorded_check_without_issue_list_can_explain_its_warning():
    old = {'status': 'warning', 'checks': [
        {'id': 'confidence_evidence_alignment', 'status': 'warning'}]}
    assert merge_content_credibility_results(old, approved())['status'] == 'passed'
