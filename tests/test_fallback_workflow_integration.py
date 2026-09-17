"""Real service adapter boundaries for preflight and actual model receipts."""
import asyncio
import copy

import pytest

import workflow_services
from agent_runtime.attempt_telemetry import record_node_model_call, record_node_model_response
from agent_runtime.deferred import AgentDeferredError
from state_memory import initialize_agent_state
from workflow_state import agent_state_to_graph
from workflow_telemetry import with_node_telemetry


class Availability:
    def __init__(self, blocked): self.blocked = blocked
    def eligible_key_slots(self, model): return set() if self.blocked else {1}
    def model_retry_wait(self, model): return 60 if self.blocked else 0
    def provider_quota_exhausted(self, model): return self.blocked


def state():
    return agent_state_to_graph(initialize_agent_state({'ticker':'TEST.TW','company_name':'Test'}), pipeline_id='v4')


@pytest.mark.parametrize('entry', ['prepare','agent'])
def test_actual_adapter_defers_before_rag_or_agent_provider_work(monkeypatch, entry):
    calls = []
    async def rag(*args): calls.append('rag')
    async def agent(*args):
        calls.append('agent')
        return args[0], 'mock valid output'
    monkeypatch.setattr(workflow_services, 'build_rag_index_async', rag)
    monkeypatch.setattr(workflow_services, 'run_agent_with_quality_gates_async', agent)
    services = workflow_services.create_default_workflow_services(rotator=Availability(True))
    graph = state()
    before = copy.deepcopy(graph)
    with pytest.raises(AgentDeferredError) as raised:
        asyncio.run(services.prepare(graph) if entry=='prepare' else services.run_agent(22, graph))
    assert raised.value.agent_num == 24
    assert calls == []
    assert graph == before


def test_actual_adapter_emits_new_response_model_not_previous_usage(monkeypatch):
    async def agent(role, data, context, *args):
        assert role not in context.get('llm_token_usage', {})
        record_node_model_call(context, role, 'gemini-3.5-flash-lite')
        record_node_model_response(context, role, 'gemini-3.5-flash-lite', {'usage': {'input_tokens': 11, 'output_tokens': 3}})
        return role, '有來源、有風險條件的測試分析。'
    monkeypatch.setattr(workflow_services, 'run_agent_with_quality_gates_async', agent)
    records=[]
    services=workflow_services.create_default_workflow_services(rotator=Availability(False),telemetry_callback=records.append)
    graph=state()
    graph['llm_token_usage']={'23': {'input_tokens':99999,'output_tokens':88888}}
    before=copy.deepcopy(graph)
    wrapped=with_node_telemetry('agent_23', lambda s: services.run_agent(23,s), services, agent_num=23)
    result=asyncio.run(wrapped(graph))
    assert records[0]['model']=='gemini-3.5-flash-lite'
    assert records[0]['input_tokens']==11
    assert records[0]['output_tokens']==3
    assert records[0]['quality_gate_pass'] is None
    assert 'llm_token_usage' not in result
    assert graph==before
