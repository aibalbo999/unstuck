import hashlib

import pytest

from memo_output_completion import incomplete_memo_roles
from structured_output_runtime import process_agent_response

GENERIC_ROLES = [1, 2, 5, 6, 12, 13, 15, 17, 18, 20]


def test_every_pipeline_role_has_generic_or_stricter_completion_contract():
    from memo_output_completion import PROVIDER_COMPLETION_AGENTS, provider_output_incomplete
    from pipeline_modes import PIPELINE_DEFINITIONS
    all_roles = {agent for mode in PIPELINE_DEFINITIONS.values() for agent in mode['agents']}
    assert all_roles == set(PROVIDER_COMPLETION_AGENTS) | {3, 4, 7, 11, 14, 16, 19, 21, 22, 23, 24}
    assert set(PROVIDER_COMPLETION_AGENTS) == set(GENERIC_ROLES)
    assert provider_output_incomplete({'output_completion': {
        'contract_version': 'provider-output-completion:v1', 'status': 'incomplete'}})


@pytest.mark.parametrize('agent', GENERIC_ROLES)
@pytest.mark.parametrize('diagnostics', [
    {'finish_reasons': ['MAX_TOKENS']}, {'finish_reasons': ['SAFETY']},
    {'finish_reasons': ['STOP'], 'stream_completed': False},
])
def test_known_incomplete_response_remains_blocked_after_reparse(agent, diagnostics):
    from final_audit import run_final_report_audit
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    from agent_runtime.repair_state import repair_contract_issues
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from workflow_services import initialize_graph_state
    from types import SimpleNamespace
    services = SimpleNamespace(progress_callback=None, cancel_check=None)
    state = initialize_graph_state({'ticker': '6282.TW', 'company_name': '康舒'}, pipeline_id='v1')
    context = legacy_context_from_graph(state, services)
    from output_sanitizer import sanitize_model_output
    raw = '<think>尚未完成的內部草稿</think>\n{"analysis_markdown":"原始段落尚未完成'
    text = process_agent_response(agent, raw, context, completion_diagnostics=diagnostics)
    process_agent_response(agent, text, context)
    process_agent_response(agent, text, context, completion_diagnostics={'stream_completed': True})
    process_agent_response(agent, sanitize_model_output(text), context)
    context['analyses'][agent] = text
    roles = incomplete_memo_roles(context)
    assert roles and roles[0]['agent'] == agent
    assert roles[0]['receipt']['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert not roles[0]['receipt'].get('raw_schema_complete')
    audit = run_final_report_audit(context, append_section=False)
    assert any(f'Agent {agent}' in issue and '供應商' in issue for issue in audit['critical'])
    assert repair_contract_issues(agent, context)
    assert not try_parse_structured_output(agent, text, context)[0]
    with pytest.raises(ReportPublicationBlockedError, match='分析未完整'):
        assert_report_publishable({'pipeline': 'v1', 'rerun_context': context, 'final_audit': {'status': 'passed'}})
    state.update(graph_delta_from_legacy_context(context))
    restored = legacy_context_from_graph(state, SimpleNamespace(progress_callback=None, cancel_check=None))
    assert incomplete_memo_roles(restored)[0]['receipt'] == roles[0]['receipt']


@pytest.mark.parametrize('agent', GENERIC_ROLES)
def test_unknown_is_not_fabricated_stop_and_new_response_does_not_inherit_old_finish(agent):
    context = {'pipeline_id': 'v1', 'data': {}}
    process_agent_response(agent, '完整舊文字。', context)
    assert not incomplete_memo_roles(context)
    receipt = (context.get('structured_outputs', {}).get(agent) or {}).get('output_completion') or {}
    assert not receipt.get('finish_reasons')
    process_agent_response(agent, '截斷文字', context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    assert incomplete_memo_roles(context)
    process_agent_response(agent, '另一份完整文字。', context, completion_diagnostics={'finish_reasons': ['STOP']})
    assert not incomplete_memo_roles(context)


@pytest.mark.parametrize('agent', GENERIC_ROLES)
def test_known_incomplete_cannot_be_written_or_read_as_successful_step_cache(monkeypatch, agent):
    from agent_runtime import step_cache
    context = {'pipeline_id': 'v1', 'data': {}}
    text = process_agent_response(agent, '未完成', context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 60)
    writes = []
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda *args, **kwargs: writes.append(args))
    step_cache.store_cached_agent_step('test', agent_num=agent, context=context, model_id='test', text=text)
    assert not writes
    cached = {'agent_num': agent, 'text': text, 'structured_output': context['structured_outputs'][agent]}
    monkeypatch.setattr(step_cache, 'get_cache_json', lambda key: cached)
    observation = {}
    assert step_cache.get_cached_agent_step('test', observation) is None
    assert observation['reason'] == 'known_provider_incomplete'
