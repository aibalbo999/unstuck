import copy

import pytest

from report_analysis_completeness import assess_report_analysis_completeness


def context(status='source_bound', direction='Long'):
    setup = {'trade_direction': direction, 'entry_zone': '30', 'target_price': '35',
             'stop_loss': '28', 'support_level': '28', 'resistance_level': '35',
             'core_catalyst': '等待已確認事件後重新評估，目前不交易。', 'risk_level': 'High',
             'source_assessment': {'status': status, 'reason_codes': [], 'repair_attempted': False}}
    if direction == 'Neutral':
        setup.update(entry_zone='N/A', target_price='N/A', stop_loss='N/A')
    return {'pipeline_id': 'v4', 'structured_outputs': {24: setup}, 'data': {'data_trust': {'status': 'fresh'}},
            'report_lint': {'status': 'passed'}, 'final_audit': {'status': 'passed'},
            'evidence_exit_gate': {'verdict': 'approved'},
            'content_credibility': {'status': 'passed'}, 'report_conformance': {'status': 'passed'}}


@pytest.mark.parametrize('source,direction,expected', [
    ('source_bound', 'Long', 'complete'), ('observation', 'Neutral', 'observation'),
    ('degraded', 'Neutral', 'degraded'), ('unknown', 'Neutral', 'quality_warning')])
def test_four_states_are_separate_from_green_quality_gates(source, direction, expected):
    payload = context(source, direction); before = copy.deepcopy(payload)
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == expected
    assert result['quality_warning'] is False
    assert payload == before


def test_no_source_contract_never_infers_complete_from_passed_gates():
    payload = context(); payload['structured_outputs'][24].pop('source_assessment')
    assert assess_report_analysis_completeness(payload)['status'] == 'quality_warning'


@pytest.mark.parametrize('prefix', ['來源不足，原方向不可執行；', '資料不足，原方向不可執行；'])
def test_legacy_system_prefix_identifies_degraded_snapshot(prefix):
    payload = context('unknown', 'Neutral'); setup = payload['structured_outputs'][24]
    setup.pop('source_assessment'); setup['core_catalyst'] = prefix + '等待重新評估'
    snapshot = {'pipeline': 'v4', 'rerun_context': payload}
    result = assess_report_analysis_completeness(snapshot)
    assert result['status'] == 'degraded'
    assert result['basis'] == 'legacy_system_prefix'


def test_user_prose_mention_is_not_a_system_degradation_prefix():
    payload = context('unknown', 'Neutral')
    payload['structured_outputs'][24]['core_catalyst'] = '對手報告寫來源不足，原方向不可執行；本次等待確認。'
    assert assess_report_analysis_completeness(payload)['status'] == 'quality_warning'


@pytest.mark.parametrize('source,expected', [('source_bound', 'quality_warning'), ('degraded', 'degraded')])
def test_warning_is_retained_alongside_completeness(source, expected):
    payload = context(source); payload['content_credibility']['warnings'] = [{'id': 'existing_warning'}]
    result = assess_report_analysis_completeness(payload)
    assert result['status'] == expected
    assert result['quality_warning'] is True


@pytest.mark.parametrize('field,value', [('target_price', 'N/A'), ('stop_loss', '40')])
def test_source_bound_cannot_hide_invalid_execution_contract(field, value):
    payload = context(); payload['structured_outputs'][24][field] = value
    assert assess_report_analysis_completeness(payload)['status'] != 'complete'


def test_missing_gates_and_unrecognized_pipeline_are_unconfirmed():
    assert assess_report_analysis_completeness({})['status'] == 'quality_warning'
    payload = context(); payload.pop('report_conformance')
    assert assess_report_analysis_completeness(payload)['status'] == 'quality_warning'


@pytest.mark.parametrize('extra', [
    {'snapshot_integrity': {'valid': False}},
    {'decision_freshness': {'status': 'needs_rerun'}},
])
def test_untrusted_or_stale_snapshot_cannot_be_certified_complete(extra):
    assert assess_report_analysis_completeness({**context(), **extra})['status'] == 'quality_warning'


def test_html_and_markdown_show_degradation_separately_from_passed_gate():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    payload = context('degraded', 'Neutral')
    for text in [build_report_reading_notice_html(payload), build_report_reading_notice_markdown(payload)]:
        assert '分析完整度' in text
        assert '資料不足降級' in text
        assert '不代表完整分析已完成' in text
        assert '已通過已知檢查' in text


def test_index_projects_legacy_degradation_without_writing_snapshot(tmp_path, monkeypatch):
    import json
    import report_index_rows
    payload = context('unknown', 'Neutral')
    payload['structured_outputs'][24].pop('source_assessment')
    payload['structured_outputs'][24]['core_catalyst'] = '來源不足，原方向不可執行；等待重新評估'
    snapshot = {'pipeline': 'v4', **payload, 'rerun_context': copy.deepcopy(payload)}
    source = tmp_path / 'sample.data.json'; source.write_text(json.dumps(snapshot), encoding='utf8')
    original = source.read_bytes()
    monkeypatch.setattr(report_index_rows, 'project_evidence_exit_gate', lambda *a: None)
    monkeypatch.setattr(report_index_rows, 'project_content_credibility_with_current_evidence', lambda *a, **kw: None)
    row = {'filename': 'TEST_v4_report_sample.html', 'ticker': 'TEST', 'company_name': 'sample',
           'report_date': '2026-09-21 16:00', 'timestamp': 1789977600, 'pipeline_id': 'v4',
           'recommendation_json': '{}', 'data_trust_json': '{}', 'data_snapshot_filename': source.name,
           'output_dir': str(tmp_path)}
    report = report_index_rows.row_to_report(row)
    assert report['analysis_completeness']['status'] == 'degraded'
    assert source.read_bytes() == original


def test_renderer_records_the_same_completeness_in_new_artifacts(monkeypatch):
    import asyncio
    import reporting.renderer as renderer
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown
    from reporting import ReportRequest
    from data_trust_snapshot_integrity import verify_data_snapshot_integrity
    async def html(ctx): return build_report_reading_notice_html(ctx)
    monkeypatch.setattr(renderer, 'generate_html_report_async', html)
    monkeypatch.setattr(renderer, 'generate_markdown_report', build_report_reading_notice_markdown)
    monkeypatch.setattr(renderer, '_lint_or_repair', lambda h,m: (h,m,{'status':'passed'}))
    monkeypatch.setattr(renderer, 'evaluate_report_evidence', lambda *a: {'verdict':'approved'})
    monkeypatch.setattr(renderer, 'evaluate_content_credibility', lambda *a, **kw: {'status':'passed'})
    monkeypatch.setattr(renderer, 'evaluate_report_conformance', lambda *a, **kw: {'status':'passed'})
    monkeypatch.setattr(renderer, 'build_data_snapshot', lambda c, **kw: copy.deepcopy(c))
    bundle = asyncio.run(renderer.ReportRenderer().render_async(ReportRequest(
        context=context('degraded', 'Neutral'), pipeline_id='v4', filename='test.html')))
    assert bundle.metadata['analysis_completeness']['status'] == 'degraded'
    assert bundle.data_snapshot['analysis_completeness'] == bundle.metadata['analysis_completeness']
    assert verify_data_snapshot_integrity(bundle.data_snapshot)['valid']
    assert '資料不足降級' in bundle.html and '資料不足降級' in bundle.markdown
