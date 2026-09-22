"""Rejected repair candidates cannot be recycled from either cache layer."""
import asyncio
from types import SimpleNamespace
import pytest
from agent_runtime import repair_loop, step_cache
import llm_semantic_cache as semantic


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('layer', ['step', 'semantic'])
@pytest.mark.parametrize('fresh_valid', [False, True])
def test_repair_gets_fresh_candidate_with_existing_request_cap(monkeypatch, asynchronous, layer, fresh_valid):
    ctx = {'pipeline_id':'v4','data':{'ticker':'2305.TW'},'ticker':'2305.TW',
           'analyses':{23:'original'},'structured_outputs':{23:{'old':True}}}
    cache = {}
    for module, enabled in [(step_cache,'AGENT_STEP_CACHE_ENABLED'),(semantic,'LLM_SEMANTIC_CACHE_ENABLED')]:
        monkeypatch.setattr(module,enabled,True)
        monkeypatch.setattr(module,'get_cache_json',lambda key: cache.get(key))
        monkeypatch.setattr(module,'set_cache_json',lambda key,value,*a:cache.__setitem__(key,value))
    monkeypatch.setattr(semantic,'LLM_SEMANTIC_CACHE_MIN_SIMILARITY',1.0)
    calls=[]
    def model(agent,data,context,rotator,**kwargs):
        cached=(step_cache.get_cached_agent_step('same') if layer=='step' else
                semantic.get_cached_llm_response('offline','same prompt',SimpleNamespace()))
        if cached:return cached['text']
        calls.append(agent)
        result='valid' if fresh_valid and len(calls)==2 else 'rejected'
        context['structured_outputs'][23]={'text':result}
        if layer=='step':step_cache.store_cached_agent_step('same',agent_num=23,context=context,model_id='offline',text=result)
        else:semantic.store_llm_response('offline','same prompt',SimpleNamespace(),text=result)
        return result
    async def async_model(*args,**kwargs):return model(*args,**kwargs)
    monkeypatch.setattr(repair_loop,'run_single_agent',model)
    monkeypatch.setattr(repair_loop,'run_single_agent_async',async_model)
    monkeypatch.setattr(repair_loop,'get_audit_rewrite_model_sequence',lambda *a:['offline'])
    monkeypatch.setattr(repair_loop,'repair_429_circuit_state',lambda *a:{})
    monkeypatch.setattr(repair_loop,'validate_analysis_output',lambda a,text,d: [] if text=='valid' else ['wrong source period'])
    for name in ['validate_company_identity','validate_prompt_leakage','repair_contract_issues']:
        monkeypatch.setattr(repair_loop,name,lambda *a:[])
    monkeypatch.setattr(repair_loop,'record_quality_fallback',lambda *a:(False,'no fallback'))
    args=(23,ctx['data'],ctx,None,['wrong source period'])
    result=asyncio.run(repair_loop._repair_agent_output_async(*args)) if asynchronous else repair_loop._repair_agent_output(*args)
    assert calls==[23,23]  # cache replay cannot spend the second repair opportunity
    assert result[0] is fresh_valid
    assert ctx['repair_attempt_counts'][23]==2  # no extra provider loop
    assert ctx['analyses'][23]==('valid' if fresh_valid else 'original')
    # The scoped repair exclusion does not clear other requests' caches.
    cached=step_cache.get_cached_agent_step('same') if layer=='step' else semantic.get_cached_llm_response('offline','same prompt',SimpleNamespace())
    assert cached


def test_scoped_repair_receipts_survive_sqlite_roundtrip_without_candidate_text(tmp_path):
    from agent_runtime.repair_candidates import repair_candidate_call, reject_candidate, observe_candidate
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from workflow_checkpoints import open_sqlite_checkpointer
    from langgraph.graph import StateGraph, START, END
    from workflow_state import AgentGraphState
    ctx={'pipeline_id':'v4','data':{'ticker':'2305.TW'},'analyses':{},'structured_outputs':{}}
    with repair_candidate_call(ctx,23,ctx['data']):
        assert step_cache.get_cached_agent_step('do not read') is None
    observe_candidate(ctx,23,ctx['data'],'secret draft')
    reject_candidate(ctx,23,ctx['data'],'secret draft',['wrong period'])
    assert 'secret draft' not in repr(ctx['repair_candidate_history'])
    async def roundtrip():
        path=tmp_path/'checkpoint.sqlite3'
        builder=StateGraph(AgentGraphState)
        builder.add_node('capture',lambda s:graph_delta_from_legacy_context(ctx))
        builder.add_edge(START,'capture');builder.add_edge('capture',END)
        config={'configurable':{'thread_id':'repair-test'}}
        async with open_sqlite_checkpointer(path) as saver:
            await builder.compile(checkpointer=saver).ainvoke({'pipeline_id':'v4','run_id':'repair-test','ticker':'2305.TW','company_name':'Test','raw_financial_data':{'input':ctx['data']}},config)
        async with open_sqlite_checkpointer(path) as saver:
            state=(await saver.aget_tuple(config)).checkpoint['channel_values']
        restored=legacy_context_from_graph(state,SimpleNamespace(progress_callback=None,cancel_check=None))
        assert restored['repair_candidate_history']==ctx['repair_candidate_history']
    asyncio.run(roundtrip())


def test_scoped_cache_policy_is_async_task_local_and_resets_after_cancel():
    from llm_cache_policy import fresh_repair_candidate, candidate_cache_read_allowed
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        async def repair():
            with fresh_repair_candidate({}):
                entered.set();await release.wait()
                assert not candidate_cache_read_allowed('raw')
                raise asyncio.CancelledError()
        async def normal():
            await entered.wait()
            assert candidate_cache_read_allowed('raw')
            release.set()
        results=await asyncio.gather(repair(),normal(),return_exceptions=True)
        assert isinstance(results[0],asyncio.CancelledError)
        assert candidate_cache_read_allowed('raw')
    asyncio.run(run())


def test_receipts_are_scoped_to_agent_input_and_contract():
    from agent_runtime import repair_candidates as policy
    ctx={'pipeline_id':'v4'};data={'ticker':'2305.TW','value':1}
    policy.reject_candidate(ctx,23,data,'candidate',['issue'])
    first=ctx['repair_candidate_history']['23']['scope_hash']
    policy.reject_candidate(ctx,24,data,'candidate',['issue'])
    assert len(ctx['repair_candidate_history'])==2
    policy.reject_candidate(ctx,23,{**data,'value':2},'different',['issue'])
    assert ctx['repair_candidate_history']['23']['scope_hash']!=first
    assert len(ctx['repair_candidate_history']['23']['rejections'])==1


@pytest.mark.parametrize('instruction',['_audit_retry_instruction','_identity_retry_instruction','_quality_retry_instruction'])
def test_public_routed_entrypoint_skips_cached_repair_but_normal_call_can_reuse(monkeypatch,instruction):
    from agent_runtime import single_agent as runtime
    import copy
    data={'ticker':'2305.TW'};ctx={'data':data,'pipeline_id':'v4','analyses':{},'structured_outputs':{}}
    cache={};calls=[]
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_ENABLED',True)
    monkeypatch.setattr(step_cache,'get_cache_json',lambda key:cache.get(key))
    monkeypatch.setattr(step_cache,'set_cache_json',lambda key,value,*a:cache.__setitem__(key,value))
    monkeypatch.setattr(runtime,'get_runtime_model_sequence',lambda *a:['offline'])
    monkeypatch.setattr(runtime,'unavailable_model',lambda *a:None)
    monkeypatch.setattr(runtime,'_build_model_prompt',lambda *a:'same prompt')
    monkeypatch.setattr(runtime,'model_key_count',lambda *a:1)
    async def admit(*args,**kwargs):return SimpleNamespace(call_provider=True,evidence_notes='')
    monkeypatch.setattr(runtime,'admit_model_input_async',admit)
    async def provider(agent,context,*args,**kwargs):
        calls.append(agent);return 'fresh from provider'
    monkeypatch.setattr(runtime,'_run_agent_once_async',provider)
    monkeypatch.setattr(runtime,'record_model_success',lambda *a:None)
    key=runtime.build_agent_step_cache_key(23,data,ctx,'offline','same prompt')
    cache[key]={'text':'old cached candidate','agent_num':23,'model_id':'offline','structured_output':{}}
    normal=copy.deepcopy(ctx)
    assert asyncio.run(runtime.run_single_agent_async(23,data,normal,None))=='old cached candidate'
    ctx[instruction]='repair this candidate'
    assert asyncio.run(runtime.run_single_agent_async(agent_num=23,data=data,context=ctx,rotator=None))=='fresh from provider'
    assert calls==[23]
