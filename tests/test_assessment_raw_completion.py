"""Truncated assessments must not acquire default scores or zero valuations."""
from copy import deepcopy
import json

import pytest

from structured_output_runtime import process_agent_response
from agent_runtime.quality_structured_outputs import try_parse_structured_output


def payload(agent):
    if agent == 3:
        from moat_assessment import MOAT_FIELDS
        return {'reasoning_steps': ['來源', '反證', '限制'],
                'moat_scores': dict.fromkeys(MOAT_FIELDS),
                'analysis_markdown': '未取得可驗證品牌與客戶留存資料，評分未評估。'}
    if agent in (4, 14):
        return {'price_targets': {'熊市情境': None, '基本情境': None, '牛市情境': None,
                'dcf_reasoning': '自由現金流為負，現金流折現不可用。',
                'peer_reasoning': '缺少同期間可比倍數。', 'scenario_reasoning': '缺少可驗證情境計算，不補造價格。'},
                'valuation_summary': {'primary_method': 'relative_valuation', 'uses_market_value_wacc': False,
                    'uses_normalized_fcf': False, 'double_counting_check': '未新增題材溢價。'},
                'analysis_markdown': '缺少可驗證情境計算，三情境皆未評估。'}
    return {'thesis_summary': '風險來源尚待核對。', 'downside_risks': [],
            'analysis_markdown': '未取得可驗證的反證，不能視為沒有風險。'}


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
@pytest.mark.parametrize('truncated', [False, True])
def test_provider_max_tokens_is_not_a_complete_assessment_even_with_valid_json(agent, truncated):
    raw = json.dumps(payload(agent), ensure_ascii=False)
    if truncated:
        raw = raw[:len(raw)//2]
    context = {'pipeline_id': 'v2' if agent == 14 else 'v1', 'data': {}, 'structured_outputs': {agent: {'old': True}}}
    result = process_agent_response(agent, raw, context, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    output = context['structured_outputs'][agent]
    assert output.get('output_completion', {}).get('status') == 'incomplete'
    assert 'moat_scores' not in output and 'price_targets' not in output
    assert not try_parse_structured_output(agent, result, context)[0]
    process_agent_response(agent, raw, context)
    assert context['structured_outputs'][agent]['output_completion']['status'] == 'incomplete'


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
def test_stop_with_missing_required_content_is_not_completed_by_defaults(agent):
    context = {'data': {}}
    process_agent_response(agent, '{"reasoning_steps":["來源"]}', context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    output = context['structured_outputs'].get(agent, {})
    assert output.get('output_completion', {}).get('status') == 'incomplete'
    assert 'moat_scores' not in output and 'price_targets' not in output


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
def test_first_parse_of_incomplete_raw_json_returns_false_not_a_receipt_only_success(agent):
    context = {'pipeline_id': 'v2' if agent == 14 else 'v1', 'data': {}}
    assert not try_parse_structured_output(agent, '{"analysis_markdown":"部分', context)[0]


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
def test_complete_explicit_unknowns_remain_unknown_not_fake_values(agent):
    context = {'data': {}}
    process_agent_response(agent, json.dumps(payload(agent), ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    output = context['structured_outputs'][agent]
    assert output.get('output_completion', {}).get('status') == 'complete'
    if agent in (4, 14):
        assert set(output['price_targets'].values()) == {None}
    if agent == 3:
        assert output['moat_assessment']['assessed_count'] == 0


@pytest.mark.parametrize('agent', [4, 14])
def test_absent_scenario_is_not_an_explicit_unknown_or_zero(agent):
    raw = payload(agent)
    del raw['price_targets']['基本情境']
    context = {'data': {}}
    process_agent_response(agent, json.dumps(raw, ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    assert context['structured_outputs'][agent]['output_completion']['status'] == 'incomplete'


@pytest.mark.parametrize('value', [True, False, 0, -1, '48.5', float('inf'), float('nan')])
def test_invalid_raw_price_is_not_sanitized_into_a_completed_scenario(value):
    raw = payload(14)
    raw['price_targets']['基本情境'] = value
    context = {'data': {}}
    process_agent_response(14, json.dumps(raw, ensure_ascii=False), context)
    assert context['structured_outputs'][14]['output_completion']['status'] == 'incomplete'


@pytest.mark.parametrize('field,value', [('scenario_reasoning', None), ('peer_reasoning', 123), ('dcf_reasoning', '')])
def test_missing_valuation_reason_cannot_be_completed_by_generic_defaults(field, value):
    raw = payload(14)
    raw['price_targets'][field] = value
    context = {'data': {}}
    process_agent_response(14, json.dumps(raw, ensure_ascii=False), context)
    assert context['structured_outputs'][14]['output_completion']['status'] == 'incomplete'


@pytest.mark.parametrize('agent', [3, 4, 7, 14, 21])
def test_observed_truncating_routes_use_low_thinking_without_increasing_output_budget(agent):
    from agent_runtime.generation_config import build_generation_config, apply_model_generation_policy, generation_profile
    for model in ('gemini-3-flash-preview', 'gemini-3.6-flash', 'gemini-3.8-flash'):
        config = apply_model_generation_policy(build_generation_config(agent), model, agent)
        assert config.thinking_config.thinking_level.lower() == 'low'
        assert config.max_output_tokens == generation_profile(agent)['max_output_tokens']


def test_unknown_scenarios_and_input_data_are_not_recalculated():
    data = {'current_price': 48.5, 'data_trust': {'score': 91}}
    before = deepcopy(data)
    context = {'data': data}
    process_agent_response(14, json.dumps(payload(14), ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    assert data == before
    assert context['structured_outputs'][14]['price_targets']['基本情境'] is None


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
def test_incomplete_assessment_cannot_be_adopted_by_repair_or_hidden_by_fallback(agent):
    from agent_runtime.structured_repair_contracts import structured_output_missing
    from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
    from final_audit import run_final_report_audit
    context = {'pipeline_id': 'v2' if agent == 14 else 'v1', 'agent_sequence': [agent],
               'data': {}, 'analyses': {agent: '模型回應尚未完整。'}}
    process_agent_response(agent, json.dumps(payload(agent), ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    before = deepcopy(context['structured_outputs'][agent])
    assert structured_output_missing(context, agent)
    assert not _deterministic_structured_fallback(agent, {}, context, context['analyses'][agent])[0]
    assert context['structured_outputs'][agent] == before
    audit = run_final_report_audit(context, append_section=False)
    assert any(f'Agent {agent} 模型評估未完整' in issue for issue in audit['critical'])
    assert agent in audit['repair_agent_issues']


@pytest.mark.parametrize('agent', [3, 4, 14, 21])
def test_old_or_incomplete_cache_cannot_supply_an_assessment(monkeypatch, agent):
    import agent_runtime.step_cache as cache
    monkeypatch.setattr(cache, 'AGENT_STEP_CACHE_ENABLED', True)
    entry = {'agent_num': agent, 'text': 'old default text', 'structured_output': payload(agent)}
    monkeypatch.setattr(cache, 'get_cache_json', lambda key: entry)
    observation = {}
    assert cache.get_cached_agent_step('test', observation) is None
    assert observation['reason'] == 'assessment_completion_unconfirmed'
    entry['structured_output']['output_completion'] = {'contract_version': 'assessment-output-completion:v1', 'status': 'incomplete'}
    assert cache.get_cached_agent_step('test') is None
    entry['structured_output']['output_completion']['status'] = 'complete'
    assert cache.get_cached_agent_step('test') is entry


def test_assessment_cache_invalidation_is_scoped_to_changed_roles(monkeypatch):
    import assessment_output_completion as completion
    from agent_runtime.step_cache import build_agent_step_cache_key
    def keys():
        return {n: build_agent_step_cache_key(n, {}, {}, 'same', 'same') for n in range(1, 25)}
    before = keys()
    monkeypatch.setattr(completion, 'CONTRACT', 'isolated-new-assessment-policy')
    after = keys()
    assert {n for n in before if before[n] != after[n]} == {3, 4, 14, 21}


def test_rejected_a_quotes_explain_missing_confidence_without_adopting_the_candidate():
    from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback
    candidate = {'recommendation': {'建議': '避免', '信心指數': '7/10'},
        'market_context_assessment': {'global_market_context': {'impact': 'affects_conclusion'}},
        'assumption_reconciliation_assessment': {'issues': ['unsupported_growth_quote']}}
    context = {'pipeline_id': 'v1', 'analyses': {}, 'structured_outputs': {7: candidate}}
    assert _deterministic_structured_fallback(7, {}, context, '')[0]
    output = context['structured_outputs'][7]
    assert '引文未通過' in output['recommendation']['信心指數']
    assert '7/10' not in output['recommendation']['信心指數']
    assert output['assessment_limitations']['rejected_candidate_adopted'] is False
    assert 'market_context_assessment' not in output
    assert '不代表所有原始財務與市場來源均缺少' in output['analysis_markdown']
