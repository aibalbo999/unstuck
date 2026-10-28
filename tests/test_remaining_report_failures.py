"""Bounded repairs for saved amount, confidence and truncated-output failures."""
import asyncio
from copy import deepcopy
import json

import pytest

from financial_money_claims import financial_money_claim_issues
from financial_output_validator import validate_analysis_output
from structured_output_models import PriceTargets
from structured_output_normalizer import normalize_structured_output


def valuation(target=43.15):
    return {'price_targets': {'dcf_reasoning': 'DCF 原件不足，未評估。',
        'peer_reasoning': '同業期間不同，保留限制。', 'scenario_reasoning': '資料信心不足，不設明確目標價。',
        '熊市情境': target, '基本情境': target, '牛市情境': target},
        'valuation_summary': {'primary_method': 'relative_valuation', 'uses_market_value_wacc': False,
            'uses_normalized_fcf': False, 'double_counting_check': '沒有將相同成長重複計價。'},
        'analysis_markdown': '資料信心低於門檻，估值暫未確認，待年度財報原件核對後重新評估。'}


@pytest.mark.parametrize('agent', [4, 14])
def test_explicit_unassessed_scenario_is_nullable_not_a_zero_price(agent):
    payload = valuation(None)
    before = deepcopy(payload)
    model = PriceTargets.model_validate(payload['price_targets'])
    assert model.model_dump(by_alias=True)['基本情境'] is None
    result = normalize_structured_output(agent, payload)
    assert result and result['price_targets'] == {key: None for key in ('熊市情境', '基本情境', '牛市情境')}
    assert result['valuation_reasoning']['scenario_reasoning'] == payload['price_targets']['scenario_reasoning']
    assert payload == before


def test_nullable_schema_still_requires_each_scenario_field():
    schema = PriceTargets.model_json_schema(by_alias=True)
    assert {'熊市情境', '基本情境', '牛市情境'} <= set(schema['required'])
    assert {'type': 'null'} in schema['properties']['基本情境']['anyOf']


@pytest.mark.parametrize('heading', ['市場預期與財務證據查核', 'Forward EPS 隱含預期檢查', '未來推估'])
def test_observed_company_amount_inside_forecast_section_is_checked(heading):
    text = (f'## {heading}\n- **跨欄位交叉比對**：Forward EPS 隱含營收規模約9.2247十億元。'
            '對照公司2025年全年營收為6.61億元（折合66.1億新台幣），反映市場的成長預期。')
    data = {'ticker': '1623.TW', 'company_name': '大東電', 'financial_currency': 'TWD',
            'years': ['2025'], 'revenue_history': [6.61]}
    assert any('財務金額單位紅線' in i for i in validate_analysis_output(17, text, data))
    assert not financial_money_claim_issues(text.replace('為6.61億元', '為66.1億元'), data)


@pytest.mark.parametrize('text', [
    '## 未來推估\n預估公司2025年全年營收為6.61億元。',
    '## 未來推估\n對照同業2025年全年營收為6.61億元。',
    '## 未來推估\n假設對照公司2025年全年營收為6.61億元。',
    '## 未來推估\n對照公司2025年Q2營收為6.61億元。',
])
def test_forecast_comparison_does_not_borrow_an_unmatched_period_or_owner(text):
    assert not financial_money_claim_issues(text, {'ticker': '1623.TW', 'financial_currency': 'TWD',
        'years': ['2025'], 'revenue_history': [6.61]})


@pytest.mark.parametrize('metric,wrong,correct', [('淨利', '1.1979', '11.979'), ('營收規模', '9.2247', '92.247')])
def test_named_forward_cross_check_keeps_billion_to_yi_conversion(metric, wrong, correct):
    data = {'ticker': '1623.TW', 'financial_currency': 'TWD', 'shares_raw': 66000000,
            'forward_eps': 18.15, 'profit_margin_raw': 1.1979 / 9.2247}
    text = f'根據data.cross_checks，Forward EPS隱含{metric}為{wrong}億元。'
    assert any('推算金額單位紅線' in i for i in validate_analysis_output(17, text, data))
    assert not any('推算金額單位紅線' in i for i in validate_analysis_output(17, text.replace(wrong, correct), data))


@pytest.mark.parametrize('model', ['gemini-3.8-flash', 'gemini-3.6-flash', 'gemini-3-flash-preview',
                                   'gemini-3.5-flash-lite', 'google:gemini-3.8-flash'])
def test_trading_decision_reserves_existing_reply_budget_without_source_truncation(model):
    from agent_runtime import generation_config as generation
    original = generation.build_generation_config(16, 'unchanged complete system')
    adjusted = generation.apply_model_generation_policy(original, model, 16)
    assert adjusted.thinking_config.thinking_level.value == 'LOW'
    assert adjusted.max_output_tokens == original.max_output_tokens == 6144
    assert adjusted.response_schema == original.response_schema
    assert adjusted.system_instruction == original.system_instruction
    assert '完整 JSON' in generation.google_safe_agent_system_instruction(16, model)
    assert 'position_plan' in generation.google_safe_agent_system_instruction(16, model)
    assert 'highly detailed' not in generation.google_safe_agent_system_instruction(16, model)


def test_known_truncation_remains_incomplete_even_if_json_can_be_parsed():
    from final_output_completion import assess_final_completion
    payload = {'recommendation': {'建議': '避免'}, 'position_plan': {'cash_pct': 100},
               'confidence_basis': {'data_gaps': ['年度原件未核實']},
               'scenario_triggers': [{'scenario': '等待資料'}], 'analysis_markdown': '完整正文'}
    assert assess_final_completion(16, json.dumps(payload), {'finish_reasons': ['MAX_TOKENS']})['status'] == 'incomplete'


@pytest.mark.parametrize('repaired_target', [None, 43.15])
def test_low_confidence_price_reaches_existing_bounded_agent_repair(monkeypatch, repaired_target):
    from agent_runtime import quality_gates as gates
    requests = []
    async def noop(*args, **kwargs):
        return None
    async def initial(*args, **kwargs):
        requests.append('initial')
        return json.dumps(valuation(), ensure_ascii=False)
    async def repaired(*args, **kwargs):
        requests.append('repair')
        return json.dumps(valuation(repaired_target), ensure_ascii=False)
    for name in ('apply_deterministic_agent_skip', 'ensure_context_digest_async', 'ensure_agent_rag_context_async',
                 'checkpoint_unvalidated_draft', 'emit_status_async'):
        monkeypatch.setattr(gates, name, noop)
    monkeypatch.setattr(gates, 'initial_or_checkpointed_draft', initial)
    monkeypatch.setattr(gates, 'run_single_agent_async', repaired)
    monkeypatch.setattr(gates, 'has_checkpointed_quality_draft', lambda: False)
    monkeypatch.setattr(gates, 'validate_company_identity', lambda *args: [])
    data = {'ticker': '6282.TW', 'company_name': '康舒', 'data_trust': {'status': 'partial', 'score': 56}}
    context = {'pipeline_id': 'v1', 'data': data, 'ticker': data['ticker'], 'analyses': {}, 'structured_outputs': {}}
    asyncio.run(gates.run_agent_with_quality_gates_async(4, data, context, object()))
    assert requests == ['initial', 'repair']
    assert context['structured_outputs'][4]['price_targets']['基本情境'] == repaired_target
    assert bool(context.get('blocking_issues')) is (repaired_target is not None)


@pytest.mark.parametrize('score,blocked', [(0, True), (56, True), (59, True), (60, False), (100, False)])
@pytest.mark.parametrize('agent', [4, 14])
def test_target_confidence_uses_unchanged_report_threshold(score, blocked, agent):
    from agent_target_confidence import target_confidence_issues, target_confidence_instruction
    data = {'data_trust': {'score': score, 'status': 'partial'}}
    payload = valuation()
    before = deepcopy(payload)
    assert bool(target_confidence_issues(agent, '', data, payload)) is blocked
    assert bool(target_confidence_instruction(agent, data)) is blocked
    assert payload == before
    assert not target_confidence_issues(agent, '', data, valuation(None))


@pytest.mark.parametrize('agent', [7, 16, 19, 24])
def test_recommendation_and_trade_targets_are_checked_without_erasing_prices(agent):
    from agent_target_confidence import target_confidence_issues
    data = {'data_trust': {'score': 56, 'status': 'partial'}}
    payload = {'recommendation': {'短期目標（3個月）': 'NT$100'}} if agent != 24 else {'target_price': 100}
    assert target_confidence_issues(agent, '', data, payload)
    assert '100' in str(payload)


def test_nullable_targets_keep_final_guardrail_and_required_reasoning():
    from report_reproducibility import build_data_confidence_controls
    data = {'status': 'partial', 'score': 56}
    permitted = build_data_confidence_controls({'structured_outputs': {4: valuation(None)}}, data)
    forbidden = build_data_confidence_controls({'structured_outputs': {4: valuation()}}, data)
    assert permitted['conclusion_guardrails']['explicit_target_price']['allowed'] is False
    assert not permitted['conclusion_guardrails']['explicit_target_price']['detected_fields']
    assert forbidden['conclusion_guardrails']['explicit_target_price']['detected_fields']


@pytest.mark.parametrize('mode', ['sync', 'async', 'stream'])
def test_agent16_preserves_full_input_and_does_not_add_generation_calls(monkeypatch, mode):
    from agent_runtime import generation_config as generation
    prompt = '完整原始來源第一行\n' + '來源數字 -1.025 billion_twd 日期2026-10-16\n' * 400 + '完整來源末行'
    observed = []
    def call(key, model, text, config, **kwargs):
        observed.append((text, config))
        return object()
    async def async_call(*args, **kwargs):
        return call(*args, **kwargs)
    monkeypatch.setattr(generation, 'generate_content', call)
    monkeypatch.setattr(generation, 'generate_content_async', async_call)
    monkeypatch.setattr(generation, 'generate_content_stream_async', async_call)
    if mode == 'sync':
        generation._generate_content('synthetic', 'gemini-3.8-flash', 16, prompt)
    elif mode == 'async':
        asyncio.run(generation._generate_content_async('synthetic', 'gemini-3.8-flash', 16, prompt))
    else:
        asyncio.run(generation._generate_content_stream_async('synthetic', 'gemini-3.8-flash', 16, prompt))
    assert len(observed) == 1 and observed[0][0] == prompt
    assert observed[0][1].max_output_tokens == 6144
    assert observed[0][1].thinking_config.thinking_level.value == 'LOW'


def test_completion_cache_invalidation_is_scoped_to_agent16(monkeypatch):
    from agent_runtime import generation_config as generation
    from agent_runtime.step_cache import build_agent_step_cache_key
    data = {'ticker': '2367.TW'}
    def keys():
        return [build_agent_step_cache_key(n, data, {}, 'gemini-3.8-flash', 'same source') for n in (14, 16, 19)]
    before = keys()
    monkeypatch.setattr(generation, 'AGENT16_COMPLETION_POLICY', 'test-policy-update')
    after = keys()
    assert before[0] == after[0] and before[2] == after[2] and before[1] != after[1]


@pytest.mark.parametrize('agent', [4, 14])
def test_low_confidence_instruction_is_present_in_actual_agent_prompt(agent):
    from agent_runtime.prompting import build_prompt
    from agent_target_confidence import target_confidence_instruction
    data = {'ticker': '6282.TW', 'company_name': '康舒', 'data_trust': {'status': 'partial', 'score': 56}}
    context = {'pipeline_id': 'v1' if agent == 4 else 'v2', 'data': data, 'analyses': {}, 'structured_outputs': {}}
    prompt = build_prompt(agent, data, context)
    assert target_confidence_instruction(agent, data) in prompt
    assert '三個必要鍵均填 null' in prompt


@pytest.mark.parametrize('prefix', ['', '依據同業data.cross_checks，', '錯誤示例：data.cross_checks，'])
def test_forward_projection_checker_does_not_bind_unqualified_or_peer_amounts(prefix):
    data = {'financial_currency': 'TWD', 'shares_raw': 66000000, 'forward_eps': 18.15, 'profit_margin_raw': 0.13}
    text = prefix + 'Forward EPS隱含淨利為1.1979億元。'
    assert not any('推算金額單位紅線' in i for i in validate_analysis_output(17, text, data))
