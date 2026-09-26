"""Mode-A capacity gains preserve the exact facts and quote language."""
import copy
import json

import pytest

from agent_runtime import prompting
from agent_runtime.generation_config import estimate_agent_input_tokens
from agent_runtime.single_agent_prompt import build_model_prompt
from prompt_builder import format_data_for_prompt
from prompt_record_tables import unpack_record_tables
from research_assumption_contract import reconciliation_sources
from state_memory import initialize_agent_state

LITE = 'gemini-3.5-flash-lite'


def payload(text):
    return json.JSONDecoder().raw_decode(text.split('【財務資料 JSON】\n', 1)[1])[0]


def restored(value):
    result = unpack_record_tables(value, strict=True)
    nested = result.get('data_freshness', {})
    if nested.get('source_freshness') == {'$ref': '#/source_freshness'}:
        nested['source_freshness'] = copy.deepcopy(result['source_freshness'])
    return result


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def evidence():
    fresh = {f'original_source_{i}': {'date': '2026-09-25', 'status': 'stale', 'warning': '來源需驗證，不是即時值'} for i in range(24)}
    records = [{'original_observation_date': '2026-09-25', 'original_source_link': f'https://example.test/{i}',
                'original_verbatim_statement': f'  來源 {i} "quoted"\n\t0 與 false 不同  ',
                'original_number_or_missing': 0 if i % 2 else None, 'original_boolean': False}
               for i in range(80)]
    del records[1]['original_number_or_missing']
    return {'ticker': 'TEST.TW', 'company_name': '測試公司', 'current_price': 950,
            'source_freshness': fresh, 'data_freshness': {'source_freshness': copy.deepcopy(fresh)},
            'institutional_trading': {'records': records}, 'data_source_notes': ['尾端反證，不得裁切']}


@pytest.mark.parametrize('model', [LITE, 'gemini-3-flash-preview'])
@pytest.mark.parametrize('repair', [False, True])
@pytest.mark.parametrize('with_state', [False, True])
def test_initial_and_repair_keep_every_fact_and_use_smaller_existing_encoding(model, repair, with_state):
    data = evidence()
    context = {'pipeline_id': 'v1', 'analyses': {4: '估值原文完整保留。', 5: '成長原文完整保留。'}}
    if with_state:
        context['agent_state'] = initialize_agent_state(data)
    if repair:
        context['_audit_retry_instruction'] = '唯一退件條件必須保留，核對原始數字。'
    before = copy.deepcopy((data, context))
    plain = format_data_for_prompt(prompting.data_for_agent_prompt(7, data), compact_json=True)

    actual = build_model_prompt(7, data, context, model, False, prompt_builder=prompting.build_prompt)

    assert canonical(restored(payload(actual))) == canonical(payload(plain))
    assert '__record_table__' in actual
    assert '有 row_keys 時代表以該鍵索引的物件' in actual
    encoded_section = actual.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0]
    assert len(encoded_section) < len(canonical(payload(plain))) * .85
    assert (data, context) == before
    assert actual.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    if repair:
        assert context['_audit_retry_instruction'] in actual


def test_catalog_removes_only_complete_same_role_contained_values():
    context = {'pipeline_id': 'v1',
               'analyses': {4: '估值全文：2025 年 EPS 10；**風險必須保留**。', 5: '成長全文：2026 年營收條件未知。'},
               'structured_outputs': {4: {'a': '2025 年 EPS 10', 'b': '**風險必須保留**', 'unique': '獨有反證不能刪'},
                                      5: {'cross_role': '2025 年 EPS 10', 'not_exact': '2026年營收條件未知'}}}
    original = copy.deepcopy(context)
    prompt = build_model_prompt(7, evidence(), context, LITE, False, prompt_builder=prompting.build_prompt)
    catalog = json.JSONDecoder().raw_decode(prompt.split('【Agent 4／5 逐字對照來源】\n', 1)[1])[0]
    sources = reconciliation_sources(context)
    for role in ('4', '5'):
        assert all(any(value in kept for kept in catalog[role]) for value in sources[role])
        assert all(kept in sources[role] for kept in catalog[role])
    assert catalog['4'] == [context['analyses'][4], '獨有反證不能刪']
    assert catalog['5'] == sources['5']  # No cross-role or fuzzy deduplication.
    assert context == original


def test_preselected_previous_json_is_compact_without_changing_values_or_source_text(monkeypatch):
    value = {'4': {'number': 0, 'missing': None, 'flag': False, 'quote': '  原文\n\t"不能改寫"  '}}
    previous = ('【提煉 Agent 結構化摘要】\n' + json.dumps(value, ensure_ascii=False, indent=2)
                + '\n\n【已解析結構化輸出】\n' + json.dumps(value, ensure_ascii=False, indent=2)
                + '\n\n【前序分析精選片段（非全文，依下一位 Agent 任務檢索）】\nSOURCE_TEXT\n  whitespace kept\n')
    seen = []
    def select(*args, **kwargs):
        seen.append(kwargs['max_total_chars'])
        return previous
    monkeypatch.setattr(prompting, '_format_previous', select)
    context = {'pipeline_id': 'v1'}
    prompt = build_model_prompt(7, evidence(), context, LITE, False, prompt_builder=prompting.build_prompt)
    for header in ('【提煉 Agent 結構化摘要】\n', '【已解析結構化輸出】\n'):
        actual = prompt.split(header, 1)[1]
        assert canonical(json.JSONDecoder().raw_decode(actual)[0]) == canonical(value)
        assert actual.startswith(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    assert previous.split('【前序分析精選片段', 1)[1] in prompt
    assert seen == [prompting.get_agent_context_budgets(7)[0]]


@pytest.mark.parametrize('marker', [
    {'__record_table__': 1, 'columns': ['source'], 'rows': [['literal source']]},
    {'__record_table__': 1, 'columns': ['source'], 'rows': [['literal source']], 'warning': 'KEEP'},
])
def test_ambiguous_source_table_marker_keeps_original_financial_representation(marker):
    data = evidence(); data['institutional_trading']['source_object'] = marker
    expected = format_data_for_prompt(prompting.data_for_agent_prompt(7, data), compact_json=True)
    prompt = build_model_prompt(7, data, {'pipeline_id': 'v1'}, LITE, False, prompt_builder=prompting.build_prompt)
    assert expected in prompt


@pytest.mark.parametrize('agent', [4, 5, 16, 19, 24])
def test_financial_encoding_change_is_scoped_to_research_final_role(agent):
    data = evidence()
    expected = format_data_for_prompt(prompting.data_for_agent_prompt(agent, data), compact_json=True)
    prompt = build_model_prompt(agent, data, {'pipeline_id': 'v1'}, LITE, False, prompt_builder=prompting.build_prompt)
    assert expected in prompt


@pytest.mark.parametrize('changed_value', [False, 1, None])
def test_candidate_with_changed_numeric_type_or_value_falls_back(monkeypatch, changed_value):
    data = evidence(); data['current_price'] = 1
    formatter = prompting.format_data_for_prompt
    expected = formatter(prompting.data_for_agent_prompt(7, data), compact_json=True)
    def candidate(payload_data, **options):
        result = formatter(payload_data, **options)
        if options.get('dense'):
            old = payload(result); new = copy.deepcopy(old)
            new['market_data']['current_price_twd'] = changed_value
            result = result.replace(json.dumps(old, ensure_ascii=False, separators=(',', ':'), allow_nan=False),
                                    json.dumps(new, ensure_ascii=False, separators=(',', ':'), allow_nan=False), 1)
        return result
    monkeypatch.setattr(prompting, 'format_data_for_prompt', candidate)
    prompt = build_model_prompt(7, data, {'pipeline_id': 'v1'}, LITE, False, prompt_builder=prompting.build_prompt)
    assert expected in prompt


@pytest.mark.parametrize('body', ['{"duplicate":0,"duplicate":1}', '{"broken":', '{"value":NaN}'])
def test_ambiguous_selected_json_is_kept_verbatim(monkeypatch, body):
    previous = '【已解析結構化輸出】\n' + body + '\n\n【前序分析精選片段】\nKEEP SOURCE'
    monkeypatch.setattr(prompting, '_format_previous', lambda *a, **k: previous)
    prompt = build_model_prompt(7, evidence(), {'pipeline_id': 'v1'}, LITE, False, prompt_builder=prompting.build_prompt)
    assert previous in prompt


def test_same_source_admits_after_lossless_encoding_without_raising_the_limit(monkeypatch):
    from agent_runtime import single_agent_admission
    data = evidence(); context = {'pipeline_id': 'v1'}
    actual = build_model_prompt(7, data, context, LITE, False, prompt_builder=prompting.build_prompt)
    with monkeypatch.context() as patch:
        patch.setattr(prompting, 'choose_financial_encoding', lambda original, candidate: original)
        original = build_model_prompt(7, data, context, LITE, False, prompt_builder=prompting.build_prompt)
    before = estimate_agent_input_tokens(7, LITE, original)
    after = estimate_agent_input_tokens(7, LITE, actual)
    limit = (before + after) // 2
    assert after < limit < before
    monkeypatch.setattr(single_agent_admission.config, 'MODEL_INPUT_TOKEN_LIMITS', {LITE: limit})
    monkeypatch.setattr(single_agent_admission.config, 'TPM_LIMITS', {})
    from llm_input_capacity import InputCapacityExceededError
    with pytest.raises(InputCapacityExceededError):
        single_agent_admission._preflight_model_input_capacity(7, LITE, original)
    single_agent_admission._preflight_model_input_capacity(7, LITE, actual)
    assert canonical(restored(payload(actual))) == canonical(payload(original))


@pytest.mark.parametrize('header', ['【已解析結構化輸出】\n', '【提煉 Agent 結構化摘要】\n'])
def test_headers_inside_source_prose_are_never_reencoded(header):
    from assistant_context import _format_previous
    from research_prompt_encoding import compact_previous_json
    quoted_json = json.dumps({'assumption': 'EPS 10', 'flag': False}, ensure_ascii=False, indent=2)
    source = '估值前提保持逐字：\n' + header + quoted_json + '\n\n原文最後一段。'
    context = {'pipeline_id': 'v1', 'analyses': {4: source}}
    selected = _format_previous(context, 7, max_total_chars=8000)
    assert header + quoted_json in selected
    assert compact_previous_json(selected) == selected
