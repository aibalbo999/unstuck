import asyncio
from agent_runtime.repair_candidates import repair_candidate_call, observe_candidate, reject_candidate
from workflow_services import initialize_graph_state, create_default_workflow_services


def test_quality_node_returns_candidate_receipts_to_graph(monkeypatch):
    data = {'ticker': '2305.TW', 'company_name': 'Test', 'current_price': 20}
    state = initialize_graph_state(data, pipeline_id='v4')
    async def quality(agent, data, context, rotator, callback):
        with repair_candidate_call(context, agent, data):
            pass
        observe_candidate(context, agent, data, 'fresh repaired output')
        return agent, 'fresh repaired output'
    monkeypatch.setattr('workflow_services.run_agent_with_quality_gates_async', quality)
    monkeypatch.setattr('workflow_services.preflight_remaining_critical_agents', lambda *a, **kw: None)
    services = create_default_workflow_services(rotator=object())
    delta = asyncio.run(services.run_agent(23, state))
    assert delta.get('repair_candidate_history', {}).get('23', {}).get('calls') == 1


def test_receipt_scope_changes_when_actual_prompt_fingerprint_changes():
    context = {'pipeline_id': 'v4', 'prompt_version': 'stable', 'prompt_fingerprint': 'a' * 64}
    data = {'ticker': '2305.TW'}
    reject_candidate(context, 23, data, 'candidate', ['issue'])
    first = context['repair_candidate_history']['23']['scope_hash']
    context['prompt_fingerprint'] = 'b' * 64
    reject_candidate(context, 23, data, 'candidate two', ['issue'])
    assert context['repair_candidate_history']['23']['scope_hash'] != first


def test_routed_transport_failure_is_not_a_distinct_analysis_candidate():
    from agent_runtime.repair_candidates import fresh_candidate_for_retry
    from agent_runtime.deferred import failed_route_result
    context = {'pipeline_id': 'v4', '_quality_retry_instruction': 'repair'}
    @fresh_candidate_for_retry
    def call(agent_num, data, context):
        return failed_route_result(agent_num, 'permanent provider configuration error', [])
    call(23, {}, context)
    assert context['repair_candidate_history']['23']['calls'] == 1
    assert context['repair_candidate_history']['23']['candidate_hashes'] == []


def test_deferred_quality_repair_receipt_survives_existing_draft_resume():
    import pytest
    from langgraph.checkpoint.memory import InMemorySaver
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft
    from agent_runtime.deferred import AgentDeferredError
    async def run():
        saver = InMemorySaver()
        data = {'ticker': '2305.TW'}
        context = {'pipeline_id': 'v4', 'data': data, 'analyses': {}, 'structured_outputs': {}}
        async def original(*args): return 'initial draft'
        with checkpoint_draft_scope(saver, 'independent-cache-review'):
            with pytest.raises(AgentDeferredError):
                async with quality_draft_node(23, {'stable': 'input'}, context):
                    await initial_or_checkpointed_draft(23, data, context, None, original)
                    with repair_candidate_call(context, 23, data):
                        raise AgentDeferredError(23, [{'model_id': 'offline', 'retry_wait_seconds': 60}])
            fresh = {'pipeline_id': 'v4', 'data': data, 'analyses': {}, 'structured_outputs': {}}
            async with quality_draft_node(23, {'stable': 'input'}, fresh):
                await initial_or_checkpointed_draft(23, data, fresh, None, original)
                assert fresh.get('repair_candidate_history', {}).get('23', {}).get('calls') == 1
    asyncio.run(run())


def test_parallel_public_nodes_merge_receipts_and_reload_sqlite(tmp_path, monkeypatch):
    from langgraph.graph import StateGraph, START, END
    from workflow_state import AgentGraphState
    from workflow_checkpoints import open_sqlite_checkpointer
    from workflow_context import legacy_context_from_graph
    data = {'ticker': '2305.TW', 'company_name': 'Test', 'current_price': 20}
    state = initialize_graph_state(data, pipeline_id='v4')
    async def quality(agent, data, context, rotator, callback):
        with repair_candidate_call(context, agent, data):
            await asyncio.sleep(0)
        observe_candidate(context, agent, data, f'fresh output {agent}')
        return agent, f'fresh output {agent}'
    monkeypatch.setattr('workflow_services.run_agent_with_quality_gates_async', quality)
    monkeypatch.setattr('workflow_services.preflight_remaining_critical_agents', lambda *a, **kw: None)
    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)
    async def node22(state): return await services.run_agent(22, state)
    async def node23(state): return await services.run_agent(23, state)
    for number, node in [(22, node22), (23, node23)]:
        name = f'agent_{number}'
        builder.add_node(name, node)
        builder.add_edge(START, name)
        builder.add_edge(name, END)
    async def run():
        path = tmp_path / 'nodes.sqlite3'
        config = {'configurable': {'thread_id': 'parallel-repair'}}
        async with open_sqlite_checkpointer(path) as saver:
            await builder.compile(checkpointer=saver).ainvoke(state, config)
        async with open_sqlite_checkpointer(path) as saver:
            saved = (await saver.aget_tuple(config)).checkpoint['channel_values']
        restored = legacy_context_from_graph(saved, services)
        assert set(restored['repair_candidate_history']) == {'22', '23'}
        assert [restored['repair_candidate_history'][str(a)]['calls'] for a in (22, 23)] == [1, 1]
    asyncio.run(run())


def test_receipt_scope_changes_when_upstream_evidence_changes():
    context = {'pipeline_id': 'v4', 'analyses': {22: 'initial upstream'}, 'structured_outputs': {}}
    data = {'ticker': '2305.TW'}
    reject_candidate(context, 24, data, 'candidate', ['issue'])
    first = context['repair_candidate_history']['24']['scope_hash']
    context['analyses'][22] = 'corrected upstream'
    reject_candidate(context, 24, data, 'candidate two', ['issue'])
    assert context['repair_candidate_history']['24']['scope_hash'] != first


def test_diagnostic_sidecar_write_failure_preserves_original_deferred_exception():
    import pytest
    from langgraph.checkpoint.memory import InMemorySaver
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node, initial_or_checkpointed_draft
    from agent_runtime.deferred import AgentDeferredError
    class FailDiagnosticWrite(InMemorySaver):
        review_write_count = 0
        async def aput(self, *args, **kwargs):
            self.review_write_count += 1
            if self.review_write_count == 2:
                raise RuntimeError('diagnostic write unavailable')
            return await super().aput(*args, **kwargs)
    async def run():
        saver = FailDiagnosticWrite()
        context = {'pipeline_id': 'v4', 'data': {}, 'analyses': {}, 'structured_outputs': {}}
        error = AgentDeferredError(23, [{'model_id': 'offline', 'retry_wait_seconds': 60}])
        async def original(*args): return 'initial draft'
        with checkpoint_draft_scope(saver, 'sidecar-failure'):
            with pytest.raises(AgentDeferredError) as caught:
                async with quality_draft_node(23, {'stable': 'input'}, context):
                    await initial_or_checkpointed_draft(23, {}, context, None, original)
                    with repair_candidate_call(context, 23, {}):
                        raise error
            assert caught.value is error
            assert saver.review_write_count == 2
    asyncio.run(run())
