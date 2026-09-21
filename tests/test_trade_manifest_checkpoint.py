"""Successful trade prompt evidence follows the real node/checkpoint path."""
import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from langgraph.graph import START, END, StateGraph
from analysis_input_provenance import freeze_analysis_inputs
from report_analysis_evidence import capture_analysis_evidence
from trade_source_contract import bind_source_prompt, source_block
from structured_output_runtime import process_agent_response
from test_trade_source_completion import setup_payload
from workflow_services import initialize_graph_state, create_default_workflow_services
from workflow_context import legacy_context_from_graph, graph_delta_from_legacy_context
from workflow_state import AgentGraphState
from workflow_checkpoints import execute_persistent_graph


def harness(monkeypatch):
    data = {'ticker':'2033.TW','company_name':'Test','current_price':100,'quant_metrics':{'rsi':60}}
    freeze_analysis_inputs(data)
    state = initialize_graph_state(data, pipeline_id='v4')
    state['analyses'] = {'22':'technical', '23':'risk'}
    seen=[]
    async def quality(agent, data, context, rotator, progress_callback):
        block,catalog,fingerprint=source_block(data)
        bind_source_prompt(context,block,block,catalog,fingerprint)
        seen.append(deepcopy(context['_trade_source_manifest']))
        payload={**setup_payload(), 'trade_direction':'Neutral', 'core_catalyst':'等待技術訊號',
                 'support_source_refs':[], 'resistance_source_refs':[], 'catalyst_source_refs':[]}
        result=process_agent_response(24,json.dumps(payload),context)
        return agent,result
    monkeypatch.setattr('workflow_services.run_agent_with_quality_gates_async', quality)
    monkeypatch.setattr('workflow_services.preflight_remaining_critical_agents', lambda *a,**kw:None)
    services=create_default_workflow_services(rotator=object())
    return state,services,seen


def test_successful_agent_manifest_survives_real_checkpoint_cold_resume(monkeypatch,tmp_path):
    state,services,seen=harness(monkeypatch)
    def graph(fail):
        builder=StateGraph(AgentGraphState)
        async def agent(state): return await services.run_agent(24,state)
        async def finish(state):
            if fail: raise RuntimeError('fixture final audit deferred')
            return {'status':'done'}
        builder.add_node('trade',agent);builder.add_node('finish',finish)
        builder.add_edge(START,'trade');builder.add_edge('trade','finish');builder.add_edge('finish',END)
        return builder
    async def run(fail,initial):
        return await execute_persistent_graph(graph_builder=graph(fail),initial_state=initial,
            thread_id='trade-manifest',checkpoint_path=tmp_path/'manifest.sqlite3')
    with pytest.raises(RuntimeError,match='fixture final audit deferred'):
        asyncio.run(run(True,state))
    resumed=asyncio.run(run(False,{}))
    assert len(seen)==1
    context=legacy_context_from_graph(resumed,services)
    assert context.get('_trade_source_manifest')==seen[0]
    packet=capture_analysis_evidence(context)
    assert packet['sections']['trade_source_manifest']['data']==seen[0]
    # A later final-audit delta must preserve the receipt, without synthesizing a catalog.
    assert graph_delta_from_legacy_context(context)['trade_source_evidence']==resumed['trade_source_evidence']


@pytest.mark.parametrize('changed',['data','upstream','output'])
def test_changed_input_or_output_cannot_reuse_saved_trade_manifest(monkeypatch,changed):
    state,services,seen=harness(monkeypatch)
    delta=asyncio.run(services.run_agent(24,state))
    assert delta.get('trade_source_evidence')
    for key,value in delta.items():
        if key in {'analyses','structured_outputs','analysis_provenance'}:
            state.setdefault(key,{}).update(value)
        else:
            state[key]=value
    assert legacy_context_from_graph(state,services).get('_trade_source_manifest')==seen[0]
    if changed=='data': state['raw_financial_data']['input']['current_price']=101
    elif changed=='upstream': state['analyses']['22']='changed technical'
    else: state['structured_outputs']['24']['core_catalyst']='changed claim'
    context=legacy_context_from_graph(state,services)
    assert '_trade_source_manifest' not in context
    assert capture_analysis_evidence(context)['sections']['trade_source_manifest']['status']=='unknown'


def test_output_cannot_be_bound_to_another_catalog_even_when_input_is_unchanged(monkeypatch):
    from workflow_trade_evidence import successful_trade_evidence
    from analysis_dependencies import record_result_provenance
    state,services,seen=harness(monkeypatch)
    delta=asyncio.run(services.run_agent(24,state))
    for key in ('analyses','structured_outputs','analysis_provenance'):
        state.setdefault(key,{}).update(delta[key])
    state['trade_source_evidence']=delta['trade_source_evidence']
    context=legacy_context_from_graph(state,services)
    context['structured_outputs'][24]['source_assessment']['source_fingerprint']='0'*64
    record_result_provenance(24,context)
    assert successful_trade_evidence(context)=={}


def test_nonserializable_input_does_not_fabricate_identity_or_break_prompt_binding():
    context={'data':{'unused':float('nan')}}
    bind_source_prompt(context,'block','block',{'safe':1},'fingerprint')
    assert context['_trade_source_manifest']['input_fingerprint']==''


def test_step_cache_retains_actual_manifest_and_rejects_unproven_legacy(monkeypatch):
    from agent_runtime import step_cache
    state,services,seen=harness(monkeypatch)
    delta=asyncio.run(services.run_agent(24,state))
    for key in ('analyses','structured_outputs','analysis_provenance'):
        state.setdefault(key,{}).update(delta[key])
    state['trade_source_evidence']=delta['trade_source_evidence']
    context=legacy_context_from_graph(state,services)
    writes=[]
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_ENABLED',True)
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_SECONDS',60)
    monkeypatch.setattr(step_cache,'set_cache_json',lambda *a:writes.append(a))
    step_cache.store_cached_agent_step('fixture',agent_num=24,context=context,model_id='fixture',text='Neutral')
    cached=writes[0][1]
    assert cached.get('trade_source_manifest')==seen[0]
    assert step_cache.cached_market_context_matches(context,24,cached,'prompt')
    legacy={k:v for k,v in cached.items() if k!='trade_source_manifest'}
    assert not step_cache.cached_market_context_matches(context,24,legacy,'prompt')
    restored={'data':context['data'],'_trade_source_manifest':{'visible':False}}
    step_cache.restore_cached_agent_step(restored,24,cached)
    assert restored['_trade_source_manifest']==seen[0]
    restored['data']={**context['data'],'current_price':101}
    step_cache.restore_cached_agent_step(restored,24,cached)
    assert '_trade_source_manifest' not in restored


def test_rejected_source_repair_restores_original_manifest():
    from agent_runtime.trade_source_repair import repair_trade_sources
    from test_trade_source_repair_integration_review import context as repair_context, degraded
    context=repair_context();text=degraded(context)
    original=deepcopy(context['_trade_source_manifest'])
    receipt={'version':1,'raw_sha256':'original','diagnostics':{'finish_reasons':['STOP']}}
    context['_trade_completion_receipt']=deepcopy(receipt)
    async def malformed(*args):
        context['_trade_source_manifest']={'visible':False,'catalog':{}}
        context['_trade_completion_receipt']={'diagnostics':{'finish_reasons':['MAX_TOKENS']}}
        return 'malformed repair'
    assert asyncio.run(repair_trade_sources(text,{},context,None,malformed))==text
    assert context['_trade_source_manifest']==original
    assert context['_trade_completion_receipt']==receipt


def test_cache_keeps_stop_receipt_without_reparsing_and_rejects_known_truncation(monkeypatch):
    from agent_runtime import step_cache, quality_structured_outputs
    state,services,seen=harness(monkeypatch)
    context=legacy_context_from_graph(state,services)
    block,catalog,fingerprint=source_block(context['data'])
    bind_source_prompt(context,block,block,catalog,fingerprint)
    text=process_agent_response(24,json.dumps(setup_payload()),context,
        completion_diagnostics={'finish_reasons':['STOP'],'stream_completed':True})
    original_receipt=deepcopy(context['_trade_completion_receipt'])
    writes=[]
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_ENABLED',True)
    monkeypatch.setattr(step_cache,'AGENT_STEP_CACHE_SECONDS',60)
    monkeypatch.setattr(step_cache,'set_cache_json',lambda *a:writes.append(a))
    step_cache.store_cached_agent_step('fixture',agent_num=24,context=context,model_id='fixture',text=text)
    cached=writes[0][1]
    restored={'pipeline_id':'v4','data':context['data']}
    restored_text=step_cache.restore_cached_agent_step(restored,24,cached)
    assert restored['_trade_completion_receipt']==original_receipt
    monkeypatch.setattr(quality_structured_outputs,'process_agent_response',lambda *a,**kw:pytest.fail('cache reparsed'))
    assert quality_structured_outputs.try_parse_structured_output(24,restored_text,restored)[0]
    assert restored['structured_outputs'][24]['source_assessment']['output_completion']['finish_reasons']==['STOP']
    truncated=deepcopy(cached)
    truncated['trade_completion_receipt']['diagnostics']['finish_reasons']=['MAX_TOKENS']
    assert not step_cache.cached_market_context_matches(context,24,truncated,'prompt')
    assert step_cache.restore_cached_agent_step(restored,24,truncated)==''
    assert not restored['structured_outputs'].get(24)
