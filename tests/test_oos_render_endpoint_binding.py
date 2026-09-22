import report_reproducibility
from oos_research.admission import evaluate_candidate
from test_oos_research import _candidate


def test_unknown_original_start_cannot_be_inferred_from_env_runtime(monkeypatch):
    monkeypatch.setenv('GIT_COMMIT', 'a' * 40)
    monkeypatch.setattr(report_reproducibility, 'runtime_code_identity',
                        lambda: {'commit': 'a' * 40, 'dirty': False})
    packet = report_reproducibility.build_reproducibility_packet({'code_dirty': False}, {}, '2026-09-22')
    assert packet['code_commit'] == packet['render_runtime_commit'] == 'a' * 40
    assert packet['analysis_start_vs_render_revision_mismatch'] is None
    candidate = _candidate()
    candidate['report'].update({k: packet[k] for k in ('code_commit', 'code_dirty',
        'render_runtime_commit', 'render_runtime_dirty', 'analysis_start_vs_render_revision_mismatch',
        'revision_provenance_scope')})
    result = evaluate_candidate(candidate, study_kind='prospective')
    assert 'missing_analysis_start_render_revision_binding' in result['reason_codes']


def test_scope_only_packet_is_new_contract_not_legacy():
    candidate = _candidate()
    candidate['report']['revision_provenance_scope'] = 'analysis_start_and_report_render_endpoints_only'
    result = evaluate_candidate(candidate, study_kind='prospective')
    assert 'missing_analysis_start_render_revision_binding' in result['reason_codes']
    assert 'invalid_render_runtime_commit' in result['reason_codes']
    assert 'missing_render_runtime_dirty' in result['reason_codes']
