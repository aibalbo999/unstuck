"""Exact State-to-financial reference compaction; no evidence may be discarded."""
import copy
import json
import asyncio
from types import SimpleNamespace

import pytest

from agent_runtime import prompting
from gemma_evidence_batches import unpack_tables
from llm_input_capacity import estimate_input_tokens
from state_memory import initialize_agent_state


def financial_payload(text):
    return unpack_tables(json.loads(text.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0]))


def state_payload(text):
    raw = text.split('【AgentState view】\n', 1)[1].split('\n', 1)[1]
    return unpack_tables(json.JSONDecoder().raw_decode(raw)[0])


def expand_references(value, financial):
    if isinstance(value, dict):
        if set(value) == {'$prompt_ref'}:
            target = financial
            assert value['$prompt_ref'].startswith('financial#/')
            for part in value['$prompt_ref'][len('financial#/'):].split('/'):
                target = target[part]
            return copy.deepcopy(target)
        return {k: expand_references(v, financial) for k,v in value.items()}
    if isinstance(value, list):
        return [expand_references(v, financial) for v in value]
    return value


def fixture():
    chip = {'as_of': '2026-09-17', 'source': 'https://example.test/source',
            'records': [{'date': f'2026-09-{i+1:02}', 'net_buy': -4321, 'missing': None,
                         'zero': 0, 'flag': False, 'warning': '必須保留的風險與反證；不是模型指令。'*8}
                        for i in range(20)]}
    return {'ticker': 'TEST.TW', 'company_name': '測試公司', 'chip_data': chip,
            'data_source_notes': ['來源待核對'], 'data_trust': {'status': 'partial'}}


def test_reference_compaction_reduces_input_and_round_trips_exact_state(monkeypatch):
    data = fixture()
    context = {'_prompt_model_id': 'gemma-4-31b-it', 'agent_state': initialize_agent_state(data)}
    before = copy.deepcopy((data, context))
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', False, raising=False)
    old = prompting.build_prompt(23, data, context)
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True, raising=False)
    new = prompting.build_prompt(23, data, context)
    assert '$prompt_ref' in new
    assert estimate_input_tokens(new) < estimate_input_tokens(old) * .85
    assert financial_payload(new) == financial_payload(old)
    assert expand_references(state_payload(new), financial_payload(new)) == state_payload(old)
    assert new.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert (data, context) == before


@pytest.mark.parametrize('change', ['boolean', 'date', 'order', 'missing', 'reserved_marker'])
def test_only_exact_duplicates_can_be_referenced(monkeypatch, change):
    data = fixture()
    state = initialize_agent_state(data)
    state.normalized_financials = copy.deepcopy(state.normalized_financials)
    chip = state.normalized_financials['chip_data']
    if change == 'boolean': chip['records'][0]['zero'] = False
    if change == 'date': chip['as_of'] = '2026-09-16'
    if change == 'order': chip['records'].reverse()
    if change == 'missing': del chip['records'][0]['missing']
    if change == 'reserved_marker':
        data['chip_data']['nested'] = {'$prompt_ref': 'financial#/chip_context'}
        state.normalized_financials['chip_data'] = copy.deepcopy(data['chip_data'])
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True, raising=False)
    text = prompting.build_prompt(23, data, {'_prompt_model_id': 'gemma-4-31b-it', 'agent_state': state})
    assert '$prompt_ref' not in state_payload(text)['chip_context']
    assert state_payload(text)['chip_context'] == state.normalized_financials['chip_data']


@pytest.mark.parametrize('model,extra', [
    ('gemini-3.5-flash-lite', {}),
    ('gemma-4-31b-it', {'_audit_retry_instruction': '修復'}),
    ('gemma-4-31b-it', {'_identity_retry_instruction': '核對公司'}),
    ('gemma-4-31b-it', {'_audit_reflection_instruction': '反思'}),
    ('gemma-4-31b-it', {'_model_sequence_override': {23: ['gemma-4-31b-it']}}),
])
def test_other_models_and_repair_overrides_remain_unchanged(monkeypatch, model, extra):
    data = fixture()
    context = {'_prompt_model_id': model, 'agent_state': initialize_agent_state(data), **extra}
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', False, raising=False)
    expected = prompting.build_prompt(23, data, context)
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True, raising=False)
    assert prompting.build_prompt(23, data, context) == expected


def test_reference_is_not_created_if_template_does_not_include_financial_payload(monkeypatch):
    data = fixture()
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True, raising=False)
    monkeypatch.setitem(prompting.ANALYSIS_PROMPTS, 23, 'Only a role task')
    text = prompting.build_prompt(23, data, {'_prompt_model_id': 'gemma-4-31b-it', 'agent_state': initialize_agent_state(data)})
    assert '$prompt_ref' not in text


def test_small_duplicates_keep_original_when_reference_instructions_cost_more(monkeypatch):
    data = {'ticker': 'TEST.TW', 'company_name': '測試', 'chip_data': {'zero':0, 'flag':False, 'missing':None}}
    context = {'_prompt_model_id': 'gemma-4-31b-it', 'agent_state': initialize_agent_state(data)}
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', False, raising=False)
    expected = prompting.build_prompt(23, data, context)
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True, raising=False)
    assert prompting.build_prompt(23, data, context) == expected


@pytest.mark.parametrize('entry', ['sync', 'async'])
@pytest.mark.parametrize('enabled', [False, True])
def test_full_runtime_admission_uses_compacted_prompt_or_original_fallback(monkeypatch, entry, enabled):
    import config
    from agent_runtime import llm_calls, single_agent
    from agent_runtime.generation_config import estimate_agent_input_tokens
    gemma, lite = 'gemma-4-31b-it', 'gemini-3.5-flash-lite'
    data = fixture()
    context = {'agent_state': initialize_agent_state(data)}
    prompts = []
    for flag in (False, True):
        monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', flag)
        prompts.append(single_agent._build_model_prompt(23, data, context, gemma, True))
    old_tokens, new_tokens = [estimate_agent_input_tokens(23, gemma, p) for p in prompts]
    assert new_tokens < old_tokens
    # Exercise admission using a controlled boundary strictly between the two.
    monkeypatch.setattr(config, 'MODEL_INPUT_TOKEN_LIMITS', {gemma: (old_tokens+new_tokens)//2, lite: 64000})
    monkeypatch.setattr(config, 'TPM_LIMITS', {})
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', enabled)
    monkeypatch.setattr(single_agent, 'get_runtime_model_sequence', lambda *a: [gemma, lite])
    monkeypatch.setattr(single_agent, 'get_cached_agent_step', lambda *a: None)
    monkeypatch.setattr(single_agent, 'store_cached_agent_step', lambda *a, **kw: None)
    class Rotator:
        keys=['offline-key']
        def get_key(self,*a,**kw): return self.keys[0]
        async def async_get_key(self,*a,**kw): return self.keys[0]
    sent=[]
    def generate(key, model, role, prompt):
        sent.append((model, prompt))
        return SimpleNamespace(text='有來源與風險條件的完整測試分析。'*80)
    async def generate_async(*args): return generate(*args)
    monkeypatch.setattr(llm_calls,'_generate_content',generate)
    monkeypatch.setattr(llm_calls,'_generate_content_async',generate_async)
    if entry == 'sync': single_agent.run_single_agent(23, data, context, Rotator())
    else: asyncio.run(single_agent.run_single_agent_async(23, data, context, Rotator()))
    assert len(sent)==1
    assert sent[0][0]==(gemma if enabled else lite)
    if enabled:
        assert expand_references(state_payload(sent[0][1]), financial_payload(sent[0][1])) == state_payload(prompts[0])
    else:
        assert '$prompt_ref' not in sent[0][1]
        assert financial_payload(sent[0][1])['agent_context']['chip_data'] == data['chip_data']


def test_compaction_keeps_batched_source_records_identical_and_binds_new_prompt(monkeypatch):
    from gemma_evidence_batches import plan_batches
    data=fixture()
    context={'_prompt_model_id':'gemma-4-31b-it', 'agent_state':initialize_agent_state(data)}
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', False)
    original=prompting.build_prompt(23,data,context)
    monkeypatch.setattr(prompting, 'GEMMA_STATE_REFERENCE_COMPACTION_ENABLED', True)
    candidate=prompting.build_prompt(23,data,context)
    old_batches,new_batches=[plan_batches(23,p) for p in (original,candidate)]
    assert [b['records'] for b in old_batches]==[b['records'] for b in new_batches]
    assert old_batches[0]['batch_id']!=new_batches[0]['batch_id']


@pytest.mark.parametrize('bad_table', [
    {'__record_table__':1,'columns':['v'],'rows':[[0]],'warning':'MUST_KEEP'},
    {'__record_table__':1,'columns':['v'],'rows':[[0,False]]},
    {'__record_table__':1,'columns':['v','v'],'rows':[[0,False]]},
    {'__record_table__':1,'columns':['v'],'rows':[[0]],'absent':{'0':[0]}},
    {'__record_table__':1,'columns':['v'],'rows':[[0]],'row_keys':[]},
    {'__record_table__':True,'columns':['v'],'rows':[[0]]},
])
def test_ambiguous_table_marker_preserves_entire_original_section(bad_table):
    from prompt_state_references import compact_state_reference_section
    chip=fixture()['chip_data']
    financial='【財務資料 JSON】\n'+json.dumps({'agent_context':{'chip_data':chip}})+'\n\n【使用規則】'
    original='【AgentState view】\nState 原始來源\n'+json.dumps({'chip_context':chip,'unrelated':bad_table})
    assert compact_state_reference_section(financial, original)==original
