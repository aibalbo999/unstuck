"""Independent end-to-end completion regressions: finish metadata may not vanish."""
import asyncio
import copy
import json
from contextlib import nullcontext
from types import SimpleNamespace

from test_trade_source_completion import setup_payload


def test_semantic_transport_cache_cannot_erase_max_tokens_finish(monkeypatch):
    import llm_transport as transport
    from structured_output_runtime import process_agent_response
    from llm_response_diagnostics import response_diagnostics
    from llm_http_providers import TextLLMResponse
    saved={}
    monkeypatch.setattr(transport,'get_cached_llm_response',lambda *a: saved.get('value'))
    def store(model,prompt,config,**kwargs):saved['value']={'model_id':model,**kwargs}
    monkeypatch.setattr(transport,'store_llm_response',store)
    monkeypatch.setattr(transport,'provider_attempt_scope',lambda *a,**k:nullcontext())
    raw=json.dumps(setup_payload())
    response=TextLLMResponse(raw,diagnostics={'finish_reasons':['MAX_TOKENS']})
    fake=SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kw:response))
    monkeypatch.setattr(transport,'generation_client',lambda *a:fake)
    first=transport.generate_content('offline','gemini-3-flash-preview','fixed prompt',None)
    ctx={};process_agent_response(24,first.text,ctx,completion_diagnostics=response_diagnostics(first))
    assert not ctx['structured_outputs'].get(24)
    second=transport.generate_content('offline','gemini-3-flash-preview','fixed prompt',None)
    resumed={};process_agent_response(24,second.text,resumed,completion_diagnostics=response_diagnostics(second))
    assert not resumed['structured_outputs'].get(24)


def test_quality_reparse_cannot_clear_provider_incomplete_verdict():
    from structured_output_runtime import process_agent_response
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    raw=json.dumps(setup_payload());ctx={'pipeline_id':'v4'}
    result=process_agent_response(24,raw,ctx,completion_diagnostics={'finish_reasons':['MAX_TOKENS']})
    assert not ctx['structured_outputs'].get(24)
    ok,_=try_parse_structured_output(24,result,ctx)
    assert not ok
    assert not ctx['structured_outputs'].get(24)


def test_cold_checkpoint_resume_preserves_incomplete_response_receipt():
    from langgraph.checkpoint.memory import InMemorySaver
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft
    from structured_output_runtime import process_agent_response
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    from output_sanitizer import sanitize_model_output
    async def run():
        saver=InMemorySaver();raw=json.dumps(setup_payload(),indent=2)
        async def generate(agent,data,ctx,rotator):
            return process_agent_response(24,raw,ctx,completion_diagnostics={'finish_reasons':['MAX_TOKENS']})
        async def should_not_generate(*args):raise AssertionError('cold resume regenerated original draft')
        with checkpoint_draft_scope(saver,'completion-review'):
            ctx={'pipeline_id':'v4','structured_outputs':{}}
            async with quality_draft_node(24,{},ctx):
                await initial_or_checkpointed_draft(24,{},ctx,None,generate)
            fresh={'pipeline_id':'v4','structured_outputs':{}}
            async with quality_draft_node(24,{},fresh):
                text=await initial_or_checkpointed_draft(24,{},fresh,None,should_not_generate)
                ok,_=try_parse_structured_output(24,sanitize_model_output(text),fresh)
                assert not ok
                assert not fresh['structured_outputs'].get(24)
    asyncio.run(run())


def test_identical_legitimate_retry_overrides_prior_incomplete_receipt():
    from structured_output_runtime import process_agent_response
    raw=json.dumps(setup_payload());ctx={}
    process_agent_response(24,raw,ctx,completion_diagnostics={'finish_reasons':['MAX_TOKENS']})
    process_agent_response(24,raw,ctx,completion_diagnostics={'finish_reasons':['STOP']})
    assert ctx['structured_outputs'][24]['source_assessment']['output_completion']['finish_reasons']==['STOP']


def test_unrelated_new_legacy_text_is_not_rejected_by_sticky_receipt():
    from structured_output_runtime import process_agent_response
    payload=setup_payload();ctx={}
    process_agent_response(24,json.dumps(payload),ctx,completion_diagnostics={'finish_reasons':['MAX_TOKENS']})
    payload['core_catalyst']='等待財報公告重新評估。'
    process_agent_response(24,json.dumps(payload),ctx)
    assert ctx['structured_outputs'].get(24)


def _memory_semantic_cache(monkeypatch):
    import llm_semantic_cache as cache
    values={}
    monkeypatch.setattr(cache,'get_cache_json',lambda key:copy.deepcopy(values.get(key)))
    monkeypatch.setattr(cache,'set_cache_json',lambda key,value,ttl:values.__setitem__(key,copy.deepcopy(value)))
    monkeypatch.setattr(cache,'LLM_SEMANTIC_CACHE_ENABLED',True)
    monkeypatch.setattr(cache,'LLM_SEMANTIC_CACHE_SECONDS',60)
    monkeypatch.setattr(cache,'LLM_SEMANTIC_CACHE_MIN_SIMILARITY',1)
    return cache,values


def test_success_cache_roundtrip_preserves_finish_and_original_raw_hash(monkeypatch):
    cache,values=_memory_semantic_cache(monkeypatch)
    from agent_runtime.generation_config import build_generation_config
    from llm_http_providers import TextLLMResponse
    from llm_response_diagnostics import response_diagnostics
    from structured_output_runtime import process_agent_response
    import hashlib
    config=build_generation_config(24);raw=json.dumps(setup_payload())
    cache.store_llm_response('offline','prompt',config,text=raw,diagnostics={'finish_reasons':['STOP']})
    cached=cache.get_cached_llm_response('offline','prompt',config)
    assert cached['completion_contract']=='trade-completion:v2'
    response=TextLLMResponse.from_cache(cached);ctx={}
    process_agent_response(24,response.text,ctx,completion_diagnostics=response_diagnostics(response))
    receipt=ctx['structured_outputs'][24]['source_assessment']['output_completion']
    assert receipt['finish_reasons']==['STOP']
    assert receipt['raw_sha256']==hashlib.sha256(raw.encode()).hexdigest()
    # Text changes cannot retain a previous response's trusted finish metadata.
    for key,item in values.items():
        if isinstance(item,dict) and item.get('response_sha256'):
            item['text'] += 'tampered'
    assert cache.get_cached_llm_response('offline','prompt',config) is None


def test_completion_cache_contract_invalidates_trade_only(monkeypatch):
    cache,_=_memory_semantic_cache(monkeypatch)
    from agent_runtime.generation_config import build_generation_config
    trade=build_generation_config(24);other=SimpleNamespace(temperature=0.2)
    with monkeypatch.context() as old:
        old.setattr(cache,'_completion_cache_contract',lambda config:None)
        cache.store_llm_response('offline','trade',trade,text=json.dumps(setup_payload()))
        cache.store_llm_response('offline','other',other,text='old nontrade response')
    assert cache.get_cached_llm_response('offline','trade',trade) is None
    assert cache.get_cached_llm_response('offline','other',other)['text']=='old nontrade response'


def test_previous_trade_source_policy_cache_cannot_bypass_new_source_rules(monkeypatch):
    cache, _ = _memory_semantic_cache(monkeypatch)
    from agent_runtime.generation_config import build_generation_config
    trade = build_generation_config(24)
    other = SimpleNamespace(temperature=0.2)
    with monkeypatch.context() as old:
        old.setattr(cache, '_completion_cache_contract', lambda config: 'trade-completion:v1' if config is trade else None)
        cache.store_llm_response('offline', 'trade', trade, text=json.dumps(setup_payload()), diagnostics={'finish_reasons': ['STOP']})
        cache.store_llm_response('offline', 'other', other, text='unchanged other cache')
    assert cache.get_cached_llm_response('offline', 'trade', trade) is None
    assert cache.get_cached_llm_response('offline', 'other', other)['text'] == 'unchanged other cache'
