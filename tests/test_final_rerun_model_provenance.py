"""Final-only model identity follows the adopted output, not the last response."""
import asyncio
import copy
from types import SimpleNamespace

import pytest

import report_rerun_service as service
from agent_runtime import audit_repair, single_agent
from agent_runtime.attempt_telemetry import record_node_model_call, record_node_model_response
from model_execution_provenance import normalized_model_executions, report_model_id
from pipeline_modes import get_structured_agent_num
from test_final_rerun_credibility import snapshot_for


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    state = SimpleNamespace(rendered=[], contexts=[], calls=[], mode='v1', string_key=False,
                            repair=None, repaired=False, cache=None, mutation=None, error=None,
                            raw_cache=False, synchronous=False)

    def output(context, agent, text):
        key = str(agent) if state.string_key else agent
        context['structured_outputs'].pop(agent, None)
        context['structured_outputs'].pop(str(agent), None)
        context['structured_outputs'][key] = {'recommendation': {'建議': '持有'}, 'analysis_markdown': text}
        return text

    def provider_sync(agent, context, rotator, model, prompt, **kwargs):
        if state.error:
            raise state.error
        state.calls.append(model)
        record_node_model_call(context, agent, model)
        response = {'diagnostics': {'cache_hit': True, 'model_id': 'raw-cache-origin'}} if state.raw_cache else {}
        record_node_model_response(context, agent, model, response)
        return output(context, agent, '## 決策\n' + ('修復候選。' if state.repaired else '原始候選。') * 30)

    async def provider(*args, **kwargs):
        return provider_sync(*args, **kwargs)

    def adopt(context, agent, data, prompt, text):
        # A visible post-provider transformation must precede provenance sealing.
        value = context['structured_outputs'].get(agent, context['structured_outputs'].get(str(agent)))
        value['market_context_assessment'] = {'fixture': 'new current projection'}
        return text + '\n\n市場資料已依本次來源處理。'

    async def generate(agent, data, context, rotator, **kwargs):
        state.contexts.append(context)
        result = (single_agent.run_single_agent(agent, data, context, rotator, max_retries=1) if state.synchronous else
                  await single_agent.run_single_agent_async(agent, data, context, rotator, max_retries=1))
        from validators import sanitize_model_output
        context['analyses'][agent] = sanitize_model_output(result)
        return agent, result

    async def rewrite(agent, data, context, rotator, issues):
        state.repaired = True
        context['analyses'][agent] = await single_agent.run_single_agent_async(agent, data, context, rotator, max_retries=1)
        if state.repair == 'deterministic':
            # Even identical text cannot attribute a policy replacement to a model.
            context.setdefault('deterministic_fallbacks', []).append({'agent_num': agent})
        return state.repair != 'rejected', 'fixture repair result'

    def audit(context, append_section=True):
        agent = get_structured_agent_num('recommendation', context)
        needs = bool(state.repair and not state.repaired)
        if state.mutation and append_section:
            if state.mutation == 'body':
                context['analyses'][agent] += '\n新增的研究結論。'
            elif state.mutation == 'structured':
                context['structured_outputs'].get(agent, context['structured_outputs'].get(str(agent)))['recommendation']['建議'] = '買入'
            elif state.mutation == 'audit':
                context['analyses'][agent] += '\n\n## 系統最終稽核\n系統附錄。'
            elif state.mutation == 'dual_body':
                context['analyses'][str(agent)] = '不一致的舊版正文'
            elif state.mutation == 'dual_structured':
                context['structured_outputs'][str(agent)] = {'recommendation': {'建議': '買入'}}
        result = {'status': 'passed', 'critical': [], 'warnings': [], 'repair_agent_issues': {},
                  'coverage_repair_agent_issues': {agent: ['optional coverage']} if needs else {}}
        if state.mutation == 'system_audit' and append_section:
            from final_audit_sections import append_final_audit_section
            result['warnings'] = ['非阻斷的系統稽核提醒。']
            append_final_audit_section(context, result)
        return result

    async def render(**kwargs):
        state.rendered.append(copy.deepcopy(kwargs['context']))
        return {'success': True}

    def restore(context, agent, cached):
        return output(context, agent, cached['text'])

    monkeypatch.setattr(service, 'KeyRotator', lambda *a: object())
    monkeypatch.setattr(service, 'run_agent_with_quality_gates_async', generate)
    monkeypatch.setattr(service, 'run_final_report_audit', audit)
    monkeypatch.setattr(service, 'parse_structured_data', lambda context: {})
    monkeypatch.setattr(service, 'render_and_save_rerun_report', render)
    monkeypatch.setattr(audit_repair, '_repair_agent_output_async', rewrite)
    monkeypatch.setattr(audit_repair, 'MAX_REPAIR_ITERATIONS', 1)
    monkeypatch.setattr(single_agent, 'get_runtime_model_sequence', lambda *a: ['repaired-model' if state.repaired else 'initial-model'])
    monkeypatch.setattr(single_agent, 'unavailable_model', lambda *a: None)
    monkeypatch.setattr(single_agent, 'model_key_count', lambda *a: 1)
    monkeypatch.setattr(single_agent, '_build_model_prompt', lambda *a: 'unchanged provider prompt')
    monkeypatch.setattr(single_agent, 'get_cached_agent_step', lambda *a: state.cache)
    monkeypatch.setattr(single_agent, 'cached_market_context_matches', lambda *a: True)
    monkeypatch.setattr(single_agent, 'restore_cached_agent_step', restore)
    monkeypatch.setattr(single_agent, 'store_cached_agent_step', lambda *a, **k: None)
    async def admission(*a, **k):
        return SimpleNamespace(evidence_notes='', call_provider=True)
    monkeypatch.setattr(single_agent, 'admit_model_input_async', admission)
    monkeypatch.setattr(single_agent, 'admit_model_input_sync', lambda *a, **k: SimpleNamespace(evidence_notes='', call_provider=True))
    monkeypatch.setattr(single_agent, '_run_agent_once_async', provider)
    monkeypatch.setattr(single_agent, '_run_agent_once', provider_sync)
    monkeypatch.setattr(single_agent, 'adopt_market_context_result', adopt)
    monkeypatch.setattr(single_agent, 'record_model_success', lambda *a: None)

    async def run():
        snapshot = snapshot_for(state.mode)
        snapshot['data']['model_id'] = 'stale-upstream-model'
        snapshot['model_executions'] = {'7': {'model_id': 'old-report-model'}}
        return await service._run_final_recommendation_rerun(filename=f'TEST_{state.mode}_report_20260906_010000.html',
            snapshot=snapshot, output_dir=str(tmp_path), report_renderer=object())
    state.run = run
    return state


def final_record(state):
    context = state.rendered[0]
    return report_model_id(context, context['data'], lambda value: '' if value is None else str(value)), normalized_model_executions(context)


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
@pytest.mark.parametrize('string_key', [False, True])
def test_successful_routed_final_output_persists_actual_model_after_market_projection(workflow, mode, string_key):
    workflow.mode, workflow.string_key = mode, string_key
    assert asyncio.run(workflow.run())['success']
    model, records = final_record(workflow)
    assert model == 'initial-model'
    assert len(records) == 1 and records[0]['agent_num'] == get_structured_agent_num('recommendation', mode)
    assert records[0]['cache_hit'] is False
    assert '市場資料已依本次來源處理。' in workflow.rendered[0]['analyses'][records[0]['agent_num']]
    assert not any(key in workflow.rendered[0] for key in ('_accepted_output_provenance', '_node_attempt_telemetry'))


@pytest.mark.parametrize('repair,expected', [('accepted', 'repaired-model'), ('rejected', 'initial-model'), ('deterministic', 'unknown')])
def test_optional_repair_transaction_carries_only_adopted_model(workflow, repair, expected):
    workflow.repair = repair
    assert asyncio.run(workflow.run())['success']
    assert workflow.calls == ['initial-model', 'repaired-model']
    model, records = final_record(workflow)
    assert model == expected
    assert bool(records) is (expected != 'unknown')
    if repair == 'rejected':
        assert '原始候選。' in workflow.rendered[0]['analyses'][7]
        assert '修復候選。' not in workflow.rendered[0]['analyses'][7]


@pytest.mark.parametrize('origin', ['original-cache-model', None])
def test_step_cache_provenance_comes_from_entry_not_requested_route(workflow, origin):
    workflow.cache = {'text': '## 決策\n已快取的完整研究。' * 20}
    if origin:
        workflow.cache['model_id'] = origin
    assert asyncio.run(workflow.run())['success']
    model, records = final_record(workflow)
    assert model == (origin or 'unknown')
    assert not workflow.calls
    if origin:
        assert records[0]['cache_hit'] is True
        assert records[0]['generation_config'] == {}
    else:
        assert records == []


def test_raw_response_cache_keeps_original_model_identity(workflow):
    workflow.raw_cache = True
    assert asyncio.run(workflow.run())['success']
    model, records = final_record(workflow)
    assert model == 'raw-cache-origin' and records[0]['cache_hit'] is True
    assert records[0]['generation_config'] == {}


@pytest.mark.parametrize('mutation,expected', [('body', 'unknown'), ('structured', 'unknown'), ('audit', 'unknown'),
                                            ('dual_body', 'unknown'), ('dual_structured', 'unknown'), ('system_audit', 'initial-model')])
def test_final_hash_validation_excludes_only_system_audit_appendix(workflow, mutation, expected):
    workflow.mutation = mutation
    assert asyncio.run(workflow.run())['success']
    model, records = final_record(workflow)
    assert model == expected
    assert bool(records) is (expected != 'unknown')


@pytest.mark.parametrize('kind', ['cancelled', 'deferred'])
def test_interrupted_final_rerun_does_not_render_or_retain_private_capture(workflow, kind):
    from agent_runtime.deferred import AgentDeferredError
    error = asyncio.CancelledError() if kind == 'cancelled' else AgentDeferredError(7, [{'model_id': 'initial-model', 'retry_wait_seconds': 60}])
    workflow.error = error
    with pytest.raises(type(error)):
        asyncio.run(workflow.run())
    assert not workflow.rendered
    assert all('_accepted_output_provenance' not in context and '_node_attempt_telemetry' not in context for context in workflow.contexts)


@pytest.mark.parametrize('cached', [False, True])
def test_sync_entry_inside_running_loop_also_seals_returned_model(workflow, cached):
    workflow.synchronous = True
    if cached:
        workflow.cache = {'text': '## 決策\n快取研究。' * 20, 'model_id': 'sync-cache-model'}
    assert asyncio.run(workflow.run())['success']
    assert final_record(workflow)[0] == ('sync-cache-model' if cached else 'initial-model')


def test_actual_fallback_route_attributes_returned_backup(workflow, monkeypatch):
    monkeypatch.setattr(single_agent, 'get_runtime_model_sequence', lambda *a: ['unavailable-primary', 'backup-model'])
    monkeypatch.setattr(single_agent, 'unavailable_model', lambda context, rotator, model:
                        {'model_id': model, 'retry_wait_seconds': 60} if model == 'unavailable-primary' else None)
    assert asyncio.run(workflow.run())['success']
    assert workflow.calls == ['backup-model']
    assert final_record(workflow)[0] == 'backup-model'


def _sealed_context(model='original-model', *, string_key=False, text='## 決策\n完整研究結論。'):
    from agent_runtime.accepted_output_provenance import seal_returned_output
    key = '7' if string_key else 7
    context = {'pipeline_id': 'v1', 'data': {}, 'analyses': {key: text},
               'structured_outputs': {key: {'analysis_markdown': text}}}
    record_node_model_response(context, 7, model, {})  # Only effective inside an initialized scope.
    return context


@pytest.mark.parametrize('kind', ['failure', 'cancelled', 'deferred'])
def test_single_repair_rollback_restores_output_bound_receipt(kind):
    from agent_runtime.accepted_output_provenance import final_rerun_provenance_scope, seal_returned_output, attach_accepted_final_model
    from agent_runtime.repair_transaction import preserve_failed_repair
    from agent_runtime.deferred import AgentDeferredError
    context = _sealed_context()
    with final_rerun_provenance_scope(context, 7):
        record_node_model_response(context, 7, 'original-model', {})
        seal_returned_output(context, 7, context['analyses'][7])
        @preserve_failed_repair
        def repair(agent, data, candidate):
            candidate['analyses'][agent] = '## 決策\n未採用的新研究。'
            record_node_model_response(candidate, agent, 'discarded-model', {})
            seal_returned_output(candidate, agent, candidate['analyses'][agent])
            if kind == 'cancelled':
                raise asyncio.CancelledError()
            if kind == 'deferred':
                raise AgentDeferredError(agent, [{'model_id': 'discarded-model', 'retry_wait_seconds': 60}])
            return False, 'not adopted'
        if kind == 'failure':
            assert repair(7, {}, context)[0] is False
        else:
            error = asyncio.CancelledError if kind == 'cancelled' else AgentDeferredError
            with pytest.raises(error):
                repair(7, {}, context)
        attach_accepted_final_model(context, 7)
        assert context['model_id'] == 'original-model'
    assert '_accepted_output_provenance' not in context


def test_model_authored_audit_header_does_not_hide_changed_post_header_body():
    from agent_runtime.accepted_output_provenance import final_rerun_provenance_scope, seal_returned_output, attach_accepted_final_model
    context = _sealed_context(string_key=True, text='## 決策\n研究結論。\n\n## 系統最終稽核\n模型自己的內容。')
    with final_rerun_provenance_scope(context, 7):
        record_node_model_response(context, 7, 'original-model', {})
        seal_returned_output(context, 7, context['analyses']['7'])
        attach_accepted_final_model(context, 7)
        assert context['model_id'] == 'original-model'
        context['analyses']['7'] += '\n新增買入結論。'
        attach_accepted_final_model(context, 7)
        assert context['model_id'] == 'unknown'


def test_capture_scope_is_nested_and_async_task_local_and_inactive_for_other_roles():
    from agent_runtime.accepted_output_provenance import final_rerun_provenance_scope, seal_returned_output, attach_accepted_final_model
    from workflow_telemetry_attribution import current_node_invocation
    untouched = _sealed_context()
    before = copy.deepcopy(untouched)
    seal_returned_output(untouched, 7, untouched['analyses'][7])
    assert untouched == before
    with final_rerun_provenance_scope(untouched, 24):
        assert current_node_invocation() is None
    assert untouched == before

    async def one(model):
        context = _sealed_context()
        with final_rerun_provenance_scope(context, 7):
            record_node_model_response(context, 7, model, {})
            seal_returned_output(context, 7, context['analyses'][7])
            await asyncio.sleep(0)
            nested = _sealed_context()
            with final_rerun_provenance_scope(nested, 7):
                record_node_model_response(nested, 7, 'nested-model', {})
                seal_returned_output(nested, 7, nested['analyses'][7])
                attach_accepted_final_model(nested, 7)
                assert nested['model_id'] == 'nested-model'
            attach_accepted_final_model(context, 7)
            assert context['model_id'] == model
        assert '_accepted_output_provenance' not in context and '_node_attempt_telemetry' not in context
        return context['model_id']
    async def run():
        return await asyncio.gather(one('model-a'), one('model-b'))
    assert asyncio.run(run()) == ['model-a', 'model-b']
    assert current_node_invocation() is None
