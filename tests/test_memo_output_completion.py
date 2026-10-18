import asyncio
import copy
import json
import pytest
from memo_output_completion import assess_memo_completion
from structured_output_runtime import process_agent_response
from report_analysis_completeness import assess_report_analysis_completeness
from report_publication_identity import publication_identity, replay_notice
from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
from decision_tracking import build_decision_tracking
from analysis_job_execution_state import execution_projection


def raw():
    return {'as_of_date': '2026-10-02', 'confidence': 'low', 'evidence_items': [{
        'finding': '已觀測法人資料，尚不能推論兩週報酬。', 'source_refs': ['institutional_trading.records'],
        'freshness_note': '2026-10-02；期間與單位依來源。', 'counterevidence': '資金流不是預測驗證。'}],
        'analysis_markdown': '尚無已確認兩週事件；等待具體日期與量價互相確認，資料矛盾時失效。'}


@pytest.mark.parametrize('reason', ['MAX_TOKENS', 'LENGTH', 'SAFETY', 'RECITATION'])
def test_provider_incomplete_even_when_json_and_body_look_complete(reason):
    assert assess_memo_completion(json.dumps(raw()), {'finish_reasons': [reason]})['status'] == 'incomplete'


@pytest.mark.parametrize('key', ['as_of_date', 'confidence', 'evidence_items', 'analysis_markdown'])
def test_missing_raw_fields_cannot_be_normalized_into_complete(key):
    payload = raw(); payload.pop(key)
    assert assess_memo_completion(json.dumps(payload), {'finish_reasons': ['STOP']})['status'] == 'incomplete'


@pytest.mark.parametrize('text', ['{"analysis_markdown": "未完', '{"analysis_markdown": "很長的文字"', json.dumps({**raw(), 'analysis_markdown': '資料不足'})])
def test_truncated_or_placeholder_output(text):
    assert assess_memo_completion(text, {'finish_reasons': ['STOP']})['status'] == 'incomplete'


def test_short_complete_contract_without_character_threshold():
    assert assess_memo_completion(json.dumps(raw()), {'finish_reasons': ['STOP']})['status'] == 'complete'


def test_runtime_preserves_receipt_without_manufacturing_content():
    context = {'pipeline_id': 'v4', 'data': {}}
    text = process_agent_response(23, json.dumps(raw()), context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    assert context['structured_outputs'][23]['output_completion']['status'] == 'incomplete'
    assert 'analysis_markdown' not in context['structured_outputs'][23]
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    try_parse_structured_output(23, text, context)
    assert context['structured_outputs'][23]['output_completion']['status'] == 'incomplete'


def partial():
    return {'pipeline_id': 'v4', 'generated_at': '2026-10-03T03:41:24+00:00',
            'structured_outputs': {'23': {'output_completion': assess_memo_completion(json.dumps(raw()), {'finish_reasons': ['MAX_TOKENS']})}}}


def test_partial_classification_notice_publication_and_tracking():
    value = partial(); before = copy.deepcopy(value)
    assert assess_report_analysis_completeness(value)['status'] == 'partial'
    assert publication_identity(value)['kind'] == 'partial_analysis'
    assert not publication_identity(value)['prediction_eligible']
    assert 'MAX_TOKENS' in replay_notice(value) and '未產生新模型' not in replay_notice(value)
    assert build_decision_tracking({}, snapshot=value)['status'] == 'excluded_incomplete'
    with pytest.raises(ReportPublicationBlockedError): assert_report_publishable(value)
    from reporting.reading_notice import build_report_reading_notice_html
    assert 'data-analysis-completeness="partial"' in build_report_reading_notice_html(value)
    assert 'data-publication-kind="partial_analysis"' in build_report_reading_notice_html(value)
    assert value == before


def test_legacy_missing_receipt_not_reclassified():
    assert publication_identity({'pipeline_id': 'v4', 'structured_outputs': {'23': raw()}})['prediction_eligible']


def test_finished_job_partial_without_mutating_original_status():
    job = {'status': 'done'}
    projected = execution_projection(job, events=[{'phase': 'analysis_output_incomplete', 'agent': 23, 'finish_reasons': ['MAX_TOKENS']}])
    assert projected['status'] == projected['execution_state'] == 'partial'
    assert projected['db_status'] == 'done' and job == {'status': 'done'}


def test_preview_generation_low_thinking_compact_contract():
    from agent_runtime.generation_config import generation_event_metadata, google_safe_agent_system_instruction
    assert generation_event_metadata(23, 'google:gemini-3-flash-preview')['thinking_level'] == 'low'
    assert generation_event_metadata(23, 'gemini-3-flash-preview')['max_output_tokens'] == 3072
    assert 'highly detailed' not in google_safe_agent_system_instruction(23, 'gemini-3-flash-preview')


def test_partial_graph_stops_dependent_role_and_publish():
    from test_workflow_graph_routing import FakeWorkflowServices
    from workflow_graph import run_analysis_workflow
    class PartialServices(FakeWorkflowServices):
        async def run_agent(self, num, state):
            delta = await super().run_agent(num, state)
            if num == 23: delta['structured_outputs'] = partial()['structured_outputs']
            return delta
    services = PartialServices()
    state = asyncio.run(run_analysis_workflow(initial_state=services.initialize({'ticker': '1301.TW'}, 'v4'), pipeline_id='v4', services=services))
    assert state['status'] == 'partial'
    assert 'agent:24' not in services.calls and 'persist_report' not in services.calls


def test_partial_excluded_before_trade_price_fetch(monkeypatch, tmp_path):
    import mode_trade_backtest as module
    import report_publication_identity as identity_module
    monkeypatch.setattr(identity_module, 'read_report_publication_identity', lambda *a: publication_identity(partial()))
    def forbidden(*a, **kw): raise AssertionError('must exclude before price fetch')
    from datetime import date
    results, skips = module.evaluate_report_trades(report={'filename': 'partial.html'}, pipeline_id='v4', generated=date(2026,10,3), as_of=date(2027,1,1), output_dir=str(tmp_path), bar_fetcher=forbidden)
    assert not results and skips[0]['reason'] == 'partial_analysis_not_prediction'


@pytest.mark.parametrize('key', ['finding', 'source_refs', 'freshness_note', 'counterevidence'])
def test_raw_evidence_item_required_fields(key):
    payload = raw(); payload['evidence_items'][0].pop(key)
    assert assess_memo_completion(json.dumps(payload), {'finish_reasons': ['STOP']})['status'] == 'incomplete'


def test_partial_guard_emits_event_without_another_model_call():
    from agent_runtime.quality_gates import _memo_partial_result
    context = partial(); events = []
    async def callback(event): events.append(event)
    assert asyncio.run(_memo_partial_result(23, '{truncated', context, callback))
    assert len(events) == 1 and events[0]['phase'] == 'analysis_output_incomplete'
    assert events[0]['retry_scheduled'] is False


def test_partial_never_written_to_step_cache(monkeypatch):
    from agent_runtime import step_cache
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 60)
    writes = []
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda *a: writes.append(a))
    step_cache.store_cached_agent_step('key', agent_num=23, context=partial(), model_id='gemini-3-flash-preview', text='partial')
    assert not writes


@pytest.mark.parametrize('agent', [22, 23])
@pytest.mark.parametrize('repair', [False, True])
def test_memo_prompt_references_preserve_every_source_and_retry(agent, repair, monkeypatch):
    from test_agent24_state_reference_capacity import _context
    from test_gemma_state_references import expand_references, financial_payload, state_payload
    from agent_runtime import prompting
    data, context = _context(); context['_prompt_model_id'] = 'gemini-3-flash-preview'
    if repair: context['_audit_retry_instruction'] = '保留原資料與反證，核對期間。'
    before_data = copy.deepcopy(data)
    with monkeypatch.context() as patch:
        patch.setattr(prompting, 'compact_state_reference_section', lambda financial, state: state)
        before = prompting.build_prompt(agent, data, context)
    after = prompting.build_prompt(agent, data, context)
    assert financial_payload(after) == financial_payload(before)
    assert expand_references(state_payload(after), financial_payload(after)) == state_payload(before)
    if repair: assert '保留原資料與反證，核對期間。' in after
    assert data == before_data
    assert len(after) < len(before)


def test_appended_correction_does_not_require_overwriting_original_memo():
    role = partial()['structured_outputs']['23']['output_completion']
    value = {'pipeline_id': 'v4', 'rerun_context': {'structured_outputs': {'23': raw()}}, 'analysis_output_completions': {'23': role}}
    before = copy.deepcopy(value)
    assert publication_identity(value)['kind'] == 'partial_analysis'
    assert assess_report_analysis_completeness(value)['status'] == 'partial'
    assert value == before


def test_browser_job_label_distinguishes_partial_from_completed():
    import shutil, subprocess
    from pathlib import Path
    node = shutil.which('node')
    if not node: pytest.skip('Node unavailable')
    js = Path(__file__).resolve().parents[1] / 'backend/static/job_execution_labels.js'
    script = "global.window={};require(process.argv[1]);const labels=window.StockAgentJobExecutionLabels;const assert=require('assert');assert.match(labels.label({execution_state:'partial',execution_health:'normal'}),/分析未完整/);assert.match(labels.details({execution_reason_code:'required_agent_output_incomplete'}),/停止自動重試/);assert.match(labels.label({execution_state:'completed'}),/已完成/);"
    subprocess.run([node, '-e', script, str(js)], check=True, capture_output=True, text=True)
