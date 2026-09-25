"""Mode B reports must expose known gaps even when their quality checks pass."""

from copy import deepcopy

import pytest

from pipeline_modes import PIPELINE_DEFINITIONS
from position_sizing_runtime import assess_position_plan
from report_analysis_completeness import assess_report_analysis_completeness


def b_context():
    plan = {
        'action': '等待', 'position_size': '0%', 'planning_context': 'unassessed',
        'entry_zone': 'N/A', 'stop_loss': 'N/A', 'risk_reward': 'N/A',
        'invalidation_condition': '等待資金基準與風險預算後重新評估。',
        'sizing_evidence': {'status': 'unassessed', 'reason': '未提供資金與持倉來源。'},
    }
    outputs = {num: {'analysis_markdown': f'Agent {num} 已保存研究內容。'}
               for num in PIPELINE_DEFINITIONS['v2']['agents']}
    outputs[20].update(guidance_tone='資料不足', confidence=0, highlights=[])
    outputs[16].update(position_plan=plan, recommendation={'建議': '買入'})
    outputs[16]['position_sizing_assessment'] = assess_position_plan(plan, {}, outputs[16]['recommendation'])
    return {
        'pipeline_id': 'v2', 'structured_outputs': outputs,
        'analyses': {num: value['analysis_markdown'] for num, value in outputs.items()},
        'parsed': {'position_plan': deepcopy(plan)},
        'data': {'data_trust': {'status': 'fresh'},
                 'earnings_call': {'transcript_available': False, 'coverage_status': 'metadata_only',
                                  'title': '法說會索引', 'summary': '', 'transcript_excerpt': ''}},
        'report_lint': {'status': 'passed'}, 'final_audit': {'status': 'passed'},
        'evidence_exit_gate': {'verdict': 'approved'}, 'content_credibility': {'status': 'passed'},
        'report_conformance': {'status': 'passed'},
    }


def test_b_passed_gates_preserve_explicit_guidance_and_sizing_gaps():
    payload = b_context()
    before = deepcopy(payload)
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'degraded'
    assert result['basis'] == 'v2_role_source_contract'
    assert result['source_status'] == 'degraded'
    assert result['quality_recorded'] is True and result['quality_warning'] is False
    assert {'agent_20_guidance_unassessed', 'earnings_call_transcript_unavailable',
            'position_sizing_unassessed'} <= set(result['reason_codes'])
    assert '逐字稿' in result['summary'] and '部位比例未評估' in result['summary']
    assert result['mode_assessment']['position_sizing_status'] == 'unassessed'
    assert result['mode_assessment']['research_status'] == 'incomplete'
    assert payload == before


def test_b_snapshot_roundtrip_preserves_the_same_gaps_with_string_agent_keys():
    payload = b_context()
    payload['structured_outputs'] = {str(k): v for k, v in payload['structured_outputs'].items()}
    payload['analyses'] = {str(k): v for k, v in payload['analyses'].items()}
    result = assess_report_analysis_completeness({'pipeline': 'v2', 'rerun_context': payload})
    assert result['status'] == 'degraded'
    assert result['mode_assessment']['missing_roles'] == []


@pytest.mark.parametrize('kind', ['missing_receipt', 'blocked_receipt', 'parsed_mismatch', 'fabricated_currency'])
def test_b_invalid_or_missing_position_receipt_never_certifies_normal_waiting(kind):
    payload = b_context()
    output = payload['structured_outputs'][16]
    if kind == 'missing_receipt':
        output.pop('position_sizing_assessment')
    elif kind == 'blocked_receipt':
        output['position_sizing_assessment']['issues'] = ['原始部位未通過']
    elif kind == 'parsed_mismatch':
        payload['parsed']['position_plan']['position_size'] = '100%'
    else:
        output['position_plan']['sizing_evidence']['currency'] = 'USD'
        payload['parsed']['position_plan'] = deepcopy(output['position_plan'])
    result = assess_report_analysis_completeness(payload)
    assert result['status'] not in {'complete', 'observation'}
    assert result['mode_assessment']['position_sizing_status'] == 'unconfirmed'
    assert 'position_sizing_contract_unconfirmed' in result['reason_codes']


def test_b_green_gates_without_role_source_evidence_remain_unconfirmed():
    payload = b_context()
    for key in ('structured_outputs', 'analyses', 'parsed', 'data'):
        payload.pop(key)
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'quality_warning'
    assert 'analysis_completeness_unconfirmed' in result['reason_codes']
    assert result['mode_assessment']['research_status'] == 'unconfirmed'


def test_b_source_availability_alone_does_not_fill_unassessed_guidance():
    payload = b_context()
    payload['data']['earnings_call'] = {'transcript_available': True, 'transcript': '已取得管理層逐字稿。'}
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'degraded'
    assert 'agent_20_guidance_unassessed' in result['reason_codes']
    assert 'earnings_call_transcript_unavailable' not in result['reason_codes']


def test_no_gap_marker_is_not_proof_of_complete_role_sources():
    payload = b_context()
    payload['structured_outputs'][20].update(guidance_tone='中性', confidence=0.8, highlights=['展望持平。'])
    payload['data']['earnings_call'] = {'transcript': '展望持平。'}
    payload['structured_outputs'][16].pop('position_sizing_assessment')
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'quality_warning'
    assert result['mode_assessment']['research_status'] == 'unconfirmed'


def test_missing_capital_alone_is_execution_unassessed_not_research_degradation():
    payload = b_context()
    payload['structured_outputs'][20].update(guidance_tone='中性', confidence=0.8, highlights=['展望持平。'])
    payload['data']['earnings_call'] = {'transcript': '展望持平。'}
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'quality_warning'
    assert result['mode_assessment']['position_sizing_status'] == 'unassessed'
    assert result['mode_assessment']['research_status'] == 'unconfirmed'
    assert result['mode_assessment']['research_gaps'] == []
    assert result['source_status'] == 'unknown'
    assert 'position_sizing_unassessed' in result['reason_codes']


@pytest.mark.parametrize('earnings', [{}, {'coverage_status': {'value': 'metadata_only'}}, {'summary': '只有二手摘要。'}])
def test_absent_or_malformed_source_contract_is_unknown_not_proven_missing(earnings):
    payload = b_context()
    payload['data']['earnings_call'] = earnings
    result = assess_report_analysis_completeness(payload)
    assert result['mode_assessment']['earnings_call_source_status'] == 'unknown'
    assert 'earnings_call_transcript_unavailable' not in result['reason_codes']


def test_missing_required_role_is_reported_even_when_other_gaps_are_known():
    payload = b_context()
    payload['structured_outputs'].pop(13)
    result = assess_report_analysis_completeness(payload)
    assert result['mode_assessment']['missing_roles'] == [13]
    assert 'required_role_output_unrecorded' in result['reason_codes']
    assert result['status'] != 'complete'


def test_b_existing_quality_warning_is_kept_with_explicit_research_gaps():
    payload = b_context()
    payload['content_credibility']['warnings'] = ['existing warning']
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'degraded'
    assert result['quality_warning'] is True


def test_b_index_projects_mode_gaps_without_modifying_saved_snapshot(tmp_path, monkeypatch):
    import json
    import report_index_rows

    payload = b_context()
    saved = {'pipeline': 'v2', **payload, 'rerun_context': deepcopy(payload)}
    source = tmp_path / 'sample.data.json'
    source.write_text(json.dumps(saved), encoding='utf8')
    before = source.read_bytes()
    monkeypatch.setattr(report_index_rows, 'project_evidence_exit_gate', lambda *a: None)
    monkeypatch.setattr(report_index_rows, 'project_content_credibility_with_current_evidence', lambda *a, **kw: None)
    row = {'filename': 'TEST_v2_report_sample.html', 'ticker': 'TEST', 'company_name': 'sample',
           'report_date': '2026-09-25 16:00', 'timestamp': 1790323200, 'pipeline_id': 'v2',
           'recommendation_json': '{}', 'data_trust_json': '{}', 'data_snapshot_filename': source.name,
           'output_dir': str(tmp_path)}
    result = report_index_rows.row_to_report(row)['analysis_completeness']
    assert result['status'] == 'degraded'
    assert result['mode_assessment']['position_sizing_status'] == 'unassessed'
    assert source.read_bytes() == before


def test_a_unassessed_assumptions_stay_unconfirmed():
    payload = b_context()
    payload['pipeline_id'] = 'v1'
    payload['structured_outputs'][7] = {'assumption_reconciliation_assessment': {'status': 'unassessed'}}
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == 'quality_warning'
    assert 'analysis_completeness_unconfirmed' in result['reason_codes']


def test_reading_notice_explains_b_gaps_without_changing_passed_gates():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    for render in (build_report_reading_notice_html, build_report_reading_notice_markdown):
        result = render(b_context())
        assert '已通過已知檢查' in result
        assert '逐字稿' in result and '部位比例未評估' in result
