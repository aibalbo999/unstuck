"""Independent offline review of final-agent source repair and durable drafts."""
import asyncio
import copy
import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from agent_runtime import quality_gates, step_cache
from agent_runtime.deferred import AgentDeferredError
from agent_runtime.trade_source_repair import repair_trade_sources
from structured_output_runtime import process_agent_response
from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft
from test_trade_source_completion import setup_payload


def context():
    return {'pipeline_id':'v4','ticker':'offline.TW','data':{},'analyses':{22:'kept22',23:'kept23'},
            'structured_outputs':{22:{'kept':22},23:{'kept':23}},
            '_trade_source_manifest':{'version':'trade-sources:v1','visible':True,'fingerprint':'fixed',
                'catalog':{'short_term_market_context':{'technical_indicators':{'availability':'available','source':'fixture','as_of':'2026-09-21','sma_20':95,'sma_5':110}}}}}


def degraded(ctx):
    payload=setup_payload();payload['support_source_refs']=[]
    return process_agent_response(24,json.dumps(payload),ctx)


def test_truncation_is_not_cached_then_structured_retry_and_source_repair_are_local(monkeypatch):
    ctx=context();upstream=copy.deepcopy(ctx['structured_outputs']);calls=[];writes=[]
    async def noop(*a,**k):pass
    async def skip(*a,**k):return None
    monkeypatch.setattr(quality_gates,'get_runtime_model_sequence',lambda *a:['offline'])
    monkeypatch.setattr(quality_gates,'apply_deterministic_agent_skip',skip)
    monkeypatch.setattr(quality_gates,'ensure_context_digest_async',noop)
    monkeypatch.setattr(quality_gates,'ensure_agent_rag_context_async',noop)
    monkeypatch.setattr(quality_gates,'emit_status_async',noop)
    monkeypatch.setattr(quality_gates,'sanitize_model_output',lambda x:x)
    for name in ('validate_analysis_output','validate_company_identity','validate_prompt_leakage'):
        monkeypatch.setattr(quality_gates,name,lambda *a:[])
    monkeypatch.setattr(quality_gates,'append_quality_warnings',lambda agent,text,data:text)
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_ENABLED',True)
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_SECONDS',60)
    monkeypatch.setattr(step_cache,'set_cache_json',lambda *a:writes.append(a))
    async def run(agent,data,ctx,rotator):
        calls.append(agent)
        payload=setup_payload()
        raw='{"trade_direction":"Long", "core_catalyst":"cut' if len(calls)==1 else json.dumps(payload)
        if len(calls)==2:
            payload['support_source_refs']=[];raw=json.dumps(payload)
        result=process_agent_response(agent,raw,ctx)
        step_cache.store_cached_agent_step(str(len(calls)),agent_num=agent,context=ctx,model_id='offline',text=result)
        return result
    monkeypatch.setattr(quality_gates,'run_single_agent_async',run)
    agent,result=asyncio.run(quality_gates.run_agent_with_quality_gates_async(24,{},ctx,None))
    assert calls==[24,24,24]
    assert [w[0] for w in writes]==['2','3']
    assert ctx['structured_outputs'][24]['source_assessment']['status']=='source_bound'
    assert ctx['structured_outputs'][24]['source_assessment']['repair_attempted'] is True
    assert {k:ctx['structured_outputs'][k] for k in (22,23)}==upstream
    assert ctx['analyses'][22]=='kept22' and ctx['analyses'][23]=='kept23'


@pytest.mark.parametrize('exception',[asyncio.CancelledError,lambda:AgentDeferredError(24,[{'model_id':'offline','retry_wait_seconds':1}])])
def test_cancel_or_defer_preserves_original_draft_and_upstream(exception):
    async def check():
        ctx=context();text=degraded(ctx);original=copy.deepcopy(ctx['structured_outputs'][24]);saver=InMemorySaver()
        async def run(*args):raise exception()
        with checkpoint_draft_scope(saver,'source-cancel-review'):
            async with quality_draft_node(24,{'fixed':'input'},ctx):
                with pytest.raises(BaseException):await repair_trade_sources(text,{},ctx,None,run)
            fresh=context()
            async with quality_draft_node(24,{'fixed':'input'},fresh):
                async def no_regeneration(*a):pytest.fail('original regenerated')
                restored=await initial_or_checkpointed_draft(24,{},fresh,None,no_regeneration)
                assert restored==text
                assert fresh['structured_outputs'][24]['source_assessment']['status']=='degraded'
                assert fresh['structured_outputs'][22]=={'kept':22}
                assert fresh['structured_outputs'][24]['entry_zone']==original['entry_zone']
        assert '_audit_retry_instruction' not in ctx and '_trade_source_repair_attempted' not in ctx
    asyncio.run(check())


def test_deferred_source_repair_is_resumable_after_availability_recovers():
    async def check():
        saver=InMemorySaver();ctx=context();text=degraded(ctx);calls=[]
        async def deferred(*a):
            calls.append('deferred');raise AgentDeferredError(24,[{'model_id':'offline','retry_wait_seconds':1}])
        async def recovered(agent,data,ctx,rotator):
            calls.append('recovered');return process_agent_response(24,json.dumps(setup_payload()),ctx)
        with checkpoint_draft_scope(saver,'source-resume-review'):
            async with quality_draft_node(24,{'fixed':'input'},ctx):
                with pytest.raises(AgentDeferredError):await repair_trade_sources(text,{},ctx,None,deferred)
            fresh=context()
            async with quality_draft_node(24,{'fixed':'input'},fresh):
                restored=await initial_or_checkpointed_draft(24,{},fresh,None,recovered)
                await repair_trade_sources(restored,{},fresh,None,recovered)
        assert calls==['deferred','recovered']
        assert fresh['structured_outputs'][24]['source_assessment']['status']=='source_bound'
    asyncio.run(check())


def test_cold_draft_resume_retains_source_binding_needed_to_attempt_repair():
    async def check():
        saver=InMemorySaver();ctx=context();manifest=copy.deepcopy(ctx['_trade_source_manifest']);calls=[]
        async def initial(agent,data,ctx,rotator):return degraded(ctx)
        async def repair(agent,data,ctx,rotator):
            calls.append(agent)
            # The real next model prompt rebuilds the same full visible block.
            ctx['_trade_source_manifest']=copy.deepcopy(manifest)
            return process_agent_response(24,json.dumps(setup_payload()),ctx)
        with checkpoint_draft_scope(saver,'source-cold-review'):
            async with quality_draft_node(24,{'fixed':'input'},ctx):
                await initial_or_checkpointed_draft(24,{},ctx,None,initial)
            fresh=context();fresh.pop('_trade_source_manifest')
            async with quality_draft_node(24,{'fixed':'input'},fresh):
                restored=await initial_or_checkpointed_draft(24,{},fresh,None,initial)
                await repair_trade_sources(restored,{},fresh,None,repair)
        assert calls==[24]
        assert fresh['structured_outputs'][24]['source_assessment']['status']=='source_bound'
    asyncio.run(check())
