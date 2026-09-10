"""Evidence-preserving small-model prompts and real admission/fallback boundaries."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from agent_runtime import llm_calls, prompting, routing, single_agent
from agent_runtime.generation_config import estimate_agent_input_tokens
from llm_input_capacity import InputCapacityExceededError
from prompt_builder import format_data_for_prompt
from state_memory import initialize_agent_state

GEMMA = 'gemma-4-31b-it'
FLASH = 'gemini-3.8-flash'


def payload(text):
    return json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])


@pytest.fixture
def evidence():
    return {
        'ticker': '6409.TW', 'company_name': '旭隼', 'current_price': 1234.5,
        'company_identity': {'stock_id': '6409', 'official_name': '旭隼', 'forbidden_aliases': ['其他公司']},
        'data_trust': {'status': 'partial', 'critical_failures': ['missing cash flow'], 'notes': ['待驗證']},
        'data_source_notes': [f'quality warning {i}' for i in range(8)],
        'source_freshness': {'recent_catalysts': {'as_of': '2026-09-09', 'status': 'stale'}},
        'recent_catalysts': [{'date': f'2026-09-{i+1:02}', 'title': f'正面或負面事件 {i}', 'url': f'https://example.test/{i}'} for i in range(8)],
        'revenue_ttm_raw': 50_000_000_000, 'total_debt_raw': 4_000_000_000,
        'years': ['2025', '2024', '2023'], 'revenue_history': [50, 40, 30],
        'institutional_trading': {'as_of': '2026-09-09', 'net_buy': -4321},
        'macro_indicators': {'interest_rate_pct': 2.5, 'as_of': '2026-09-09'},
    }


def test_gemma_serialization_preserves_full_payload_for_financial_roles(evidence):
    data = prompting.data_for_agent_prompt(13, evidence)
    expected = payload(format_data_for_prompt(data))
    context = {'_prompt_model_id': GEMMA, '_primary_probe_prompt': True}
    actual = unpack_tables(payload(prompting.build_prompt(13, evidence, context)))
    assert actual == expected
    assert len(json.dumps(actual, ensure_ascii=False)) < len(format_data_for_prompt(data))


@pytest.mark.parametrize('role', [11, 15, 17, 20, 22, 23])
def test_role_projection_keeps_quality_identity_sources_and_all_news(evidence, role):
    context = {'_prompt_model_id': GEMMA, '_primary_probe_prompt': True, 'agent_state': initialize_agent_state(evidence)}
    before = copy.deepcopy((evidence, context['agent_state']))
    full = payload(format_data_for_prompt(prompting.data_for_agent_prompt(role, evidence)))
    text = prompting.build_prompt(role, evidence, context)
    actual = unpack_tables(payload(text))
    for key in ('unit_contract', 'company', 'data_trust', 'data_source_notes', 'source_freshness', 'source_audit_summary', 'cross_checks'):
        if key == 'data_source_notes':
            key = 'data_quality_notes'
        expected = copy.deepcopy(full[key])
        if key == 'company':
            expected['identity'].pop('same_industry_peers')
        assert actual[key] == expected
    assert actual['market_catalysts'] == full['market_catalysts']
    assert len(actual['market_catalysts']['items']) == 8
    assert actual['prompt_scope']['agent_num'] == role
    assert actual['prompt_scope']['omitted_sections']
    assert '其他公司' in text
    assert text.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert (evidence, context['agent_state']) == before
    if role == 11:
        assert 'deterministic_financial_tool_results' not in actual
        assert actual['agent_context']['macro_indicators']['interest_rate_pct'] == 2.5
    if role in (15, 23):
        assert actual['institutional_trading']['net_buy'] == -4321


def test_flash_and_quality_rewrites_keep_full_financial_scope(evidence):
    for model, extra in ((FLASH, {}), (GEMMA, {'_audit_retry_instruction': 'Recheck missing evidence'})):
        prompt = prompting.build_prompt(11, evidence, {'_prompt_model_id': model, **extra})
        actual = payload(prompt)
        assert 'prompt_scope' not in actual
        assert 'deterministic_financial_tool_results' in actual


def test_gemma_does_not_append_a_second_identical_rag_block(evidence, monkeypatch):
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 11, '{{ fin_data }}\n{{ rag_context }}')
    context = {'_prompt_model_id': GEMMA, 'rag_context': {11: 'EXACT_SOURCE_WITH_DATE_AND_PATH'}}
    assert prompting.build_prompt(11, evidence, context).count('EXACT_SOURCE_WITH_DATE_AND_PATH') == 1


@pytest.mark.parametrize('entry', ['async', 'sync_in_loop'])
@pytest.mark.parametrize('oversize', [False, True])
def test_actual_model_prompt_admission_and_full_evidence_fallback(evidence, monkeypatch, entry, oversize):
    monkeypatch.setattr(single_agent, 'get_runtime_model_sequence', lambda *_: [GEMMA, FLASH])
    monkeypatch.setattr(single_agent, 'get_cached_agent_step', lambda *_: None)
    monkeypatch.setattr(single_agent, 'store_cached_agent_step', lambda *a, **kw: None)
    if oversize:
        evidence['recent_catalysts'].append({'title': '必須保留的反證' * 5000, 'url': 'https://example.test/negative'})
    sent = []
    class Rotator:
        keys = ['offline-key']
        def get_key(self, model, tokens, **kw):
            if model == GEMMA and tokens > 12000:
                raise InputCapacityExceededError(model, tokens, 12000, 'local_input_budget')
            return self.keys[0]
        async def async_get_key(self, *args, **kw):
            return self.get_key(*args, **kw)
    def generate(key, model, role, prompt):
        sent.append((model, unpack_tables(payload(prompt))))
        return SimpleNamespace(text='有來源與限制的完整總經分析。' * 100)
    async def generate_async(*a):
        return generate(*a)
    monkeypatch.setattr(llm_calls, '_generate_content', generate)
    monkeypatch.setattr(llm_calls, '_generate_content_async', generate_async)
    context = {}
    async def run():
        if entry == 'sync_in_loop':
            return single_agent.run_single_agent(11, evidence, context, Rotator())
        return await single_agent.run_single_agent_async(11, evidence, context, Rotator())
    assert '完整總經分析' in asyncio.run(run())
    assert len(sent) == 1
    assert sent[0][0] == (FLASH if oversize else GEMMA)
    if oversize:
        assert 'prompt_scope' not in sent[0][1]
        assert sent[0][1]['market_catalysts']['items'][-1] == evidence['recent_catalysts'][-1]
    else:
        assert sent[0][1]['prompt_scope']['agent_num'] == 11
    assert '_prompt_model_id' not in context


def test_dense_record_tables_are_lossless_and_materially_smaller(evidence):
    data = prompting.data_for_agent_prompt(13, evidence)
    data['company_identity']['same_industry_peers'] = [
        {'stock_id': str(1000+i), 'stock_name': f'同業 {i}'} for i in range(60)
    ]
    baseline = payload(format_data_for_prompt(data))
    text = format_data_for_prompt(data, dense=True)
    encoded = payload(text)
    assert unpack_tables(encoded) == baseline
    raw_size = len(json.dumps(baseline, ensure_ascii=False, separators=(',', ':')))
    assert len(json.dumps(encoded, ensure_ascii=False, separators=(',', ':'))) < raw_size * .9
    assert 'columns' in text and 'rows' in text


def unpack_tables(value):
    # Independent expansion of the documented prompt encoding, not production code.
    if isinstance(value, dict):
        if value.get('__record_table__') == 1:
            records = [dict(zip(value['columns'], map(unpack_tables, row))) for row in value['rows']]
            return dict(zip(value['row_keys'], records)) if 'row_keys' in value else records
        return {k: unpack_tables(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack_tables(v) for v in value]
    return value


def test_unrelated_industry_registry_does_not_crowd_out_role_evidence(evidence):
    evidence['company_identity']['same_industry_peers'] = [{'stock_id': '9999', 'stock_name': '同產業登錄名單'}]
    prompt = prompting.build_prompt(11, evidence, {'_prompt_model_id': GEMMA})
    small = unpack_tables(payload(prompt))
    assert 'same_industry_peers' not in small['company']['identity']
    assert 'company.identity.same_industry_peers' in small['prompt_scope']['omitted_fields']
    full = payload(prompting.build_prompt(11, evidence, {'_prompt_model_id': FLASH}))
    assert full['company']['identity']['same_industry_peers'] == evidence['company_identity']['same_industry_peers']
    assert small['company']['identity']['official_name'] == full['company']['identity']['official_name']
    assert small['company']['identity']['forbidden_aliases'] == full['company']['identity']['forbidden_aliases']


@pytest.mark.parametrize('records', [
    [{'date': f'2026-09-{i:02}', 'long_numeric_field': None if i == 1 else 0, 'long_boolean_field': False, 'long_source_field': f'https://example.test/{i}'} for i in range(1, 9)],
    [{'same': 1}, {'same': None, 'extra': False}, {'same': '1'}],
    {2020+i: {'long_numeric_field': i, 'long_source_field': 'exact source'} for i in range(10)},
    [{i: 'numeric key' * 5, 'value': i} for i in range(8)],
])
def test_table_round_trip_matches_json_types_and_missing_fields(records):
    from prompt_record_tables import pack_record_tables
    expected = json.loads(json.dumps(records, ensure_ascii=False))
    packed = json.loads(json.dumps(pack_record_tables(records), ensure_ascii=False))
    assert unpack_tables(packed) == expected


def test_gemma_preserves_sources_when_generic_context_guard_would_clip(evidence, monkeypatch):
    monkeypatch.setattr(prompting, 'get_agent_prompt_token_budget', lambda _: 100)
    prompt = prompting.build_prompt(11, evidence, {'_prompt_model_id': GEMMA})
    assert len(unpack_tables(payload(prompt))['market_catalysts']['items']) == 8
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)


def test_model_prompt_flags_restore_even_when_building_fails(evidence, monkeypatch):
    def fail(*args):
        raise ValueError('invalid source data')
    monkeypatch.setattr(single_agent, 'build_prompt', fail)
    context = {'_prompt_model_id': 'outer-model', '_primary_probe_prompt': False}
    before = dict(context)
    with pytest.raises(ValueError):
        single_agent._build_model_prompt(11, evidence, context, GEMMA, True)
    assert context == before


@pytest.mark.parametrize('flag', ['_audit_retry_instruction', '_audit_reflection_instruction', '_identity_retry_instruction'])
def test_first_flash_repair_receives_late_counterevidence_and_warnings(evidence, flag):
    context = {flag: 'recheck the last source', '_model_sequence_override': {11: [FLASH, 'gemini-3.6-flash']}}
    text = single_agent._build_model_prompt(11, evidence, context, FLASH, True)
    actual = unpack_tables(payload(text))
    assert actual['market_catalysts']['items'][-1] == evidence['recent_catalysts'][-1]
    assert actual['data_quality_notes'][-1] == evidence['data_source_notes'][-1]
    assert len(actual['market_catalysts']['items']) == 8
