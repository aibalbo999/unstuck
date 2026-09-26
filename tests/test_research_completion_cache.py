"""A7 completion observations survive reparse, rollback, restart and caching."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from structured_output_runtime import process_agent_response
from test_research_quote_fidelity import candidate


def payload():
    return candidate(quote='')


def context():
    return {'pipeline_id': 'v1', 'data': {'ticker': '6488.TWO', 'current_price': 100},
            'analyses': {}, 'structured_outputs': {}}


def generate(ctx, raw=None, reason='STOP'):
    raw = raw if raw is not None else json.dumps(payload(), ensure_ascii=False)
    diagnostics = {'finish_reasons': [reason]} if reason is not None else None
    return process_agent_response(7, raw, ctx, completion_diagnostics=diagnostics)


@pytest.mark.parametrize('reason', ['MAX_TOKENS', 'LENGTH', 'SAFETY', 'RECITATION'])
def test_known_incomplete_completion_cannot_create_structured_research(reason):
    ctx = context()
    generate(ctx, reason=reason)
    assert not ctx['structured_outputs'].get(7)


@pytest.mark.parametrize('ending', ['root', 'nested', 'string'])
def test_unclosed_raw_is_not_completed_by_json_repair(ending):
    ctx = context()
    raw = json.dumps(payload(), ensure_ascii=False)
    if ending == 'root':
        raw = raw[:-1]  # Last nested object is closed; root is not.
    elif ending == 'nested':
        raw = raw[:raw.index('"checks"')] + '"checks": ['
    else:
        raw = '{"analysis_markdown":"未完成'
    generate(ctx, raw, reason=None)
    assert not ctx['structured_outputs'].get(7)


def test_sanitized_quality_reparse_cannot_erase_incomplete_finish():
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    from output_sanitizer import sanitize_model_output
    ctx = context()
    text = generate(ctx, reason='MAX_TOKENS')
    ok, _ = try_parse_structured_output(7, sanitize_model_output(text), ctx)
    assert not ok
    assert not ctx['structured_outputs'].get(7)


def test_empty_diagnostics_reparse_is_not_proof_of_a_new_complete_response():
    ctx = context()
    raw = json.dumps(payload(), ensure_ascii=False)
    generate(ctx, raw, 'MAX_TOKENS')
    process_agent_response(7, raw, ctx, completion_diagnostics={})
    assert not ctx['structured_outputs'].get(7)


def test_new_stop_supersedes_same_raw_incomplete_and_unrelated_legacy_is_not_sticky():
    ctx = context()
    raw = json.dumps(payload(), ensure_ascii=False)
    generate(ctx, raw, 'MAX_TOKENS')
    generate(ctx, raw, 'STOP')
    assert ctx['structured_outputs'].get(7)
    assert ctx['_research_completion_receipt']['diagnostics']['finish_reasons'] == ['STOP']
    generate(ctx, raw, 'MAX_TOKENS')
    changed = payload()
    changed['analysis_markdown'] += '等待新財報驗證。'
    generate(ctx, json.dumps(changed, ensure_ascii=False), reason=None)
    assert ctx['structured_outputs'].get(7)
    assert ctx['_research_completion_receipt']['diagnostics']['finish_reasons'] == []


def test_quality_draft_cold_sqlite_resume_keeps_incomplete_receipt(tmp_path):
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    from output_sanitizer import sanitize_model_output
    async def run():
        path = tmp_path/'draft.sqlite3'
        async def initial(agent, data, ctx, rotator): return generate(ctx, reason='MAX_TOKENS')
        async def forbidden(*a): pytest.fail('cold restart generated another initial response')
        async with open_sqlite_checkpointer(path) as saver:
            with checkpoint_draft_scope(saver, 'research-completion'):
                ctx = context()
                async with quality_draft_node(7, {}, ctx):
                    await initial_or_checkpointed_draft(7, ctx['data'], ctx, None, initial)
        async with open_sqlite_checkpointer(path) as saver:
            with checkpoint_draft_scope(saver, 'research-completion'):
                restored = context()
                async with quality_draft_node(7, {}, restored):
                    text = await initial_or_checkpointed_draft(7, restored['data'], restored, None, forbidden)
                    ok, _ = try_parse_structured_output(7, sanitize_model_output(text), restored)
                    assert not ok
                    assert restored['_research_completion_receipt']['diagnostics']['finish_reasons'] == ['MAX_TOKENS']
    asyncio.run(run())


def test_market_projection_does_not_register_unrelated_text_under_prior_receipt():
    from market_context_manifest import CONTRACT_VERSION, adopt_market_context_result
    ctx = context()
    ctx['market_context_contract_version'] = CONTRACT_VERSION
    generate(ctx, reason='MAX_TOKENS')
    receipt = copy.deepcopy(ctx['_research_completion_receipt'])
    other = payload(); other['analysis_markdown'] += '不同的來源回應。'
    raw = json.dumps(other, ensure_ascii=False)
    adopt_market_context_result(ctx, 7, ctx['data'], 'prompt', raw)
    assert ctx['_research_completion_receipt'] == receipt
    generate(ctx, raw, reason=None)
    assert ctx['structured_outputs'].get(7)


@pytest.mark.parametrize('original_reason', ['MAX_TOKENS', 'STOP'])
def test_failed_repair_rolls_back_matching_original_completion_receipt(original_reason):
    from agent_runtime.repair_transaction import preserve_failed_repair
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    ctx = context()
    original = generate(ctx, reason=original_reason)
    receipt = copy.deepcopy(ctx.get('_research_completion_receipt'))
    @preserve_failed_repair
    def rejected(agent, data, candidate):
        generate(candidate, reason='STOP' if original_reason == 'MAX_TOKENS' else 'MAX_TOKENS')
        return False, 'rejected candidate'
    rejected(7, ctx['data'], ctx)
    assert receipt is not None
    assert ctx['_research_completion_receipt'] == receipt
    assert try_parse_structured_output(7, original, ctx)[0] is (original_reason == 'STOP')


def memory_cache(monkeypatch):
    from agent_runtime import step_cache
    values = {}
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 60)
    monkeypatch.setattr(step_cache, 'get_cache_json', lambda k: copy.deepcopy(values.get(k)))
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda k, v, *a: values.__setitem__(k, copy.deepcopy(v)))
    return step_cache, values


def test_step_cache_refuses_known_incomplete_even_if_a_structured_draft_is_present(monkeypatch):
    cache, values = memory_cache(monkeypatch)
    valid = context(); generate(valid)
    ctx = context(); text = generate(ctx, reason='MAX_TOKENS')
    ctx['structured_outputs'][7] = valid['structured_outputs'][7]
    cache.store_cached_agent_step('bad', agent_num=7, context=ctx, model_id='offline', text=text)
    assert 'bad' not in values


def test_step_cache_reads_reject_old_partial_structured_drafts(monkeypatch):
    cache, values = memory_cache(monkeypatch)
    values['bad'] = {'agent_num': 7, 'text': 'malformed draft', 'structured_output': {
        'recommendation': {'建議': '持有'},
        'assumption_reconciliation_assessment': {'issues': ['missing_or_invalid_assumption_reconciliation']}}}
    assert cache.get_cached_agent_step('bad') is None
    restored = context()
    assert cache.restore_cached_agent_step(restored, 7, values['bad']) == ''
    assert not restored['structured_outputs'].get(7)


@pytest.mark.parametrize('issues', [[{}], [12], {'unknown': True}, 'missing', {}, 0, None])
def test_malformed_completion_assessment_is_a_cache_miss(monkeypatch, issues):
    cache, values = memory_cache(monkeypatch)
    ctx = context(); text = generate(ctx)
    cache.store_cached_agent_step('legacy', agent_num=7, context=ctx, model_id='offline', text=text)
    values['legacy'].pop('research_completion_receipt')
    values['legacy']['structured_output']['assumption_reconciliation_assessment']['issues'] = issues
    assert cache.get_cached_agent_step('legacy') is None


def test_legacy_recommendation_alone_is_not_a_complete_research_cache_entry(monkeypatch):
    cache, values = memory_cache(monkeypatch)
    values['legacy'] = {'agent_num':7, 'text':'既有研究文字', 'structured_output':{'recommendation':{'建議':'持有'}}}
    assert cache.get_cached_agent_step('legacy') is None


def test_complete_stop_and_legacy_step_cache_roundtrip(monkeypatch):
    cache, values = memory_cache(monkeypatch)
    ctx = context(); text = generate(ctx)
    cache.store_cached_agent_step('complete', agent_num=7, context=ctx, model_id='offline', text=text)
    assert cache.get_cached_agent_step('complete')
    restored = context()
    assert cache.restore_cached_agent_step(restored, 7, values['complete']) == text
    assert restored['_research_completion_receipt'] == ctx['_research_completion_receipt']
    legacy = copy.deepcopy(values['complete'])
    legacy.pop('research_completion_receipt', None)
    values['legacy'] = legacy
    assert cache.get_cached_agent_step('legacy')
    assert cache.restore_cached_agent_step(context(), 7, legacy) == text
    damaged = copy.deepcopy(values['complete'])
    damaged['research_completion_receipt']['diagnostics']['finish_reasons'] = ['MAX_TOKENS']
    values['damaged'] = damaged
    assert cache.get_cached_agent_step('damaged') is None


@pytest.mark.parametrize('mutation', ['text', 'output', 'raw_hash'])
def test_step_cache_completion_receipt_is_bound_to_its_candidate(monkeypatch, mutation):
    cache, values = memory_cache(monkeypatch)
    ctx = context(); text = generate(ctx)
    cache.store_cached_agent_step('complete', agent_num=7, context=ctx, model_id='offline', text=text)
    saved = values['complete']
    if mutation == 'text':
        saved['text'] += '被改寫的結論'
    elif mutation == 'output':
        saved['structured_output']['recommendation']['長期目標（12個月）'] = '9999'
    else:
        saved['research_completion_receipt'].pop('raw_sha256')
    assert cache.get_cached_agent_step('complete') is None


@pytest.mark.parametrize('reason', ['STOP', 'MAX_TOKENS'])
def test_routed_completion_with_actual_market_source_projection(monkeypatch, reason):
    from agent_runtime import single_agent as runtime
    from market_context_manifest import CONTRACT_VERSION, build_source_blocks, record_prompt_manifest
    from market_context_assessment import assess_final_market_context
    cache, values = memory_cache(monkeypatch)
    initial = context()
    initial['data']['global_market_context'] = {'items': [{'symbol': 'US10Y', 'latest': 5.162, 'description': '公債殖利率'}]}
    initial['market_context_contract_version'] = CONTRACT_VERSION
    calls = []
    monkeypatch.setattr(runtime, 'get_runtime_model_sequence', lambda *a: ['offline'])
    monkeypatch.setattr(runtime, 'unavailable_model', lambda *a: None)
    monkeypatch.setattr(runtime, 'model_key_count', lambda *a: 1)
    def prompt(agent, data, ctx, *a):
        blocks = build_source_blocks(data, agent_num=7)
        text = '\n'.join(block['text'] for block in blocks)
        return record_prompt_manifest(ctx, data, agent, text, blocks)
    monkeypatch.setattr(runtime, '_build_model_prompt', prompt)
    async def admit(*a, **k): return SimpleNamespace(call_provider=True, evidence_notes='')
    async def provider(agent, ctx, *a, **k):
        calls.append(agent)
        value = payload()
        refs = ctx['_market_context_attempt_manifests'][7]['sources']['global_market_context']['visible_refs']
        value['market_context_assessment'] = {'global_market_context': {'impact': 'affects_conclusion',
            'reason': '公債殖利率增加估值折現壓力。', 'source_refs': refs}}
        return generate(ctx, json.dumps(value, ensure_ascii=False), reason)
    monkeypatch.setattr(runtime, 'admit_model_input_async', admit)
    monkeypatch.setattr(runtime, '_run_agent_once_async', provider)
    monkeypatch.setattr(runtime, 'record_model_success', lambda *a: None)
    first, second = copy.deepcopy(initial), copy.deepcopy(initial)
    a = asyncio.run(runtime.run_single_agent_async(7, first['data'], first, None))
    if reason == 'MAX_TOKENS':
        from agent_runtime.quality_structured_outputs import try_parse_structured_output
        assert not values
        assert not try_parse_structured_output(7, a, first)[0]
        assert not first['structured_outputs'].get(7)
        return
    b = asyncio.run(runtime.run_single_agent_async(7, second['data'], second, None))
    assert a == b
    assert calls == [7]
    assert second['agent_step_cache']['hits'] == 1
    assessment = assess_final_market_context(second)
    assert assessment['checks'][0]['status'] == 'passed'
    assert second['_research_completion_receipt']['diagnostics']['finish_reasons'] == ['STOP']


@pytest.mark.parametrize('shape',['missing_root_open','missing_root_both','prefix_empty_object','suffix_unclosed'])
def test_incomplete_outer_raw_is_not_json_repaired_into_complete(shape):
    raw=json.dumps(payload(),ensure_ascii=False)
    if shape=='missing_root_open':raw=raw[1:]
    elif shape=='missing_root_both':raw=raw[1:-1]
    elif shape=='prefix_empty_object':raw='來源提示 {}\n'+raw[:-1]
    else:raw=raw+'\n{"analysis_markdown":"unfinished'
    ctx=context()
    process_agent_response(7,raw,ctx,completion_diagnostics={'finish_reasons':['STOP']})
    assert not ctx['structured_outputs'].get(7)

@pytest.mark.parametrize('spacing',['compact','pretty'])
def test_sanitized_real_market_projection_preserves_max_receipt(spacing):
    from market_context_manifest import CONTRACT_VERSION, build_source_blocks,record_prompt_manifest,adopt_market_context_result
    from output_sanitizer import sanitize_model_output
    ctx=context();ctx['market_context_contract_version']=CONTRACT_VERSION
    ctx['data']['global_market_context']={'items':[{'symbol':'US10Y','latest':5.1,'description':'公債殖利率'}]}
    blocks=build_source_blocks(ctx['data'],agent_num=7)
    prompt='\n'.join(b['text'] for b in blocks)
    record_prompt_manifest(ctx,ctx['data'],7,prompt,blocks)
    value=payload();value['analysis_markdown']='研究結論\n\n\n缺乏完整證據，不假設完整。'
    raw=json.dumps(value,ensure_ascii=False,indent=2 if spacing=='pretty' else None)
    text=generate(ctx,raw,'MAX_TOKENS')
    projected=adopt_market_context_result(ctx,7,ctx['data'],prompt,text)
    sanitized=sanitize_model_output(projected)
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    ok,_=try_parse_structured_output(7,sanitized,ctx)
    assert not ok
    assert ctx['_research_completion_receipt']['diagnostics']['finish_reasons']==['MAX_TOKENS']


def test_cache_store_does_not_bless_unrelated_text_with_existing_stop_receipt(monkeypatch):
    cache,values=memory_cache(monkeypatch)
    ctx=context();generate(ctx)
    cache.store_cached_agent_step('other',agent_num=7,context=ctx,model_id='offline',text='完全不同且未驗證的結論，目標價9999。')
    assert 'other' not in values


def test_market_then_real_quality_sanitizer_cannot_resurrect_max_partial_schema():
    from market_context_manifest import CONTRACT_VERSION, build_source_blocks,record_prompt_manifest,adopt_market_context_result
    from output_sanitizer import sanitize_model_output
    ctx=context();ctx['market_context_contract_version']=CONTRACT_VERSION
    blocks=build_source_blocks(ctx['data'],agent_num=7)
    prompt='\n'.join(b['text'] for b in blocks)
    record_prompt_manifest(ctx,ctx['data'],7,prompt,blocks)
    value=payload();value.pop('analysis_markdown')
    raw='\n'+json.dumps(value,ensure_ascii=False)
    text=generate(ctx,raw,'MAX_TOKENS')
    projected=adopt_market_context_result(ctx,7,ctx['data'],prompt,text)
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    ok,_=try_parse_structured_output(7,sanitize_model_output(projected),ctx)
    assert not ok
    assert not ctx['structured_outputs'].get(7)
    assert ctx['_research_completion_receipt']['diagnostics']['finish_reasons']==['MAX_TOKENS']


@pytest.mark.parametrize('syntax', ['fenced', 'minor_trailing_comma'])
def test_complete_root_keeps_supported_json_syntax(syntax):
    raw = json.dumps(payload(), ensure_ascii=False)
    raw = '```json\n' + raw + '\n```' if syntax == 'fenced' else raw[:-1] + ',}'
    ctx = context()
    generate(ctx, raw)
    assert ctx['structured_outputs'].get(7)
    assert ctx['_research_completion_receipt']['diagnostics']['finish_reasons'] == ['STOP']
