# LangGraph Durable Analysis Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the production DAG loop with a persistent LangGraph `StateGraph` whose validation/repair routing, configured Agent nodes, parallel groups, retries, and checkpoint recovery are first-class workflow behavior.

**Architecture:** A JSON-compatible TypedDict is the checkpoint schema, while the existing Pydantic `AgentState` remains the domain validator. One graph is built per pipeline definition; isolated Agent nodes return deltas merged by reducers, and `AsyncSqliteSaver` resumes failed RQ jobs by stable `job_id`/`thread_id`.

**Tech Stack:** Python 3.13, Pydantic 2, LangGraph 1.2.6, langgraph-checkpoint-sqlite 3.1.0, aiosqlite, RQ, pytest.

---

## File Structure

- Modify `backend/requirements.txt` and `backend/requirements.lock`: add pinned LangGraph dependencies.
- Create `backend/workflow_state.py`: `AgentGraphState`, reducers, Pydantic adapters, serializable RAG adapters.
- Create `backend/workflow_graph.py`: node services, topology builder, conditional routes, retry policy, execution and resume API.
- Modify `backend/agent_state.py`: add JSON validation helpers without changing current domain fields.
- Modify `backend/agent_runtime/pipeline_runner.py`: invoke the graph rather than `pipeline.py`.
- Modify `backend/pipeline_async.py`: retain only a compatibility wrapper; remove DAG group execution.
- Modify `backend/pipeline.py`: keep public sync/async exports routed to `AnalysisPipelineRunner` without circular imports.
- Modify `backend/analysis_jobs.py`: pass stable `job_id` as workflow thread id and preserve it across RQ retries.
- Modify `backend/job_store.py`: mark rate-limited workflows `waiting_retry`.
- Test `tests/test_workflow_state.py`, `tests/test_workflow_graph_routing.py`, `tests/test_workflow_checkpoint_resume.py`, and pipeline regression tests.

### Task 1: Add and lock LangGraph dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.lock`
- Modify: `tests/test_supply_chain_audit.py`

- [ ] **Step 1: Add a failing dependency contract test**

Extend the normalized-requirement test:

```python
def test_langgraph_dependencies_are_direct_and_locked():
    direct = normalized_requirement_names(BACKEND / "requirements.txt")
    locked = normalized_requirement_names(BACKEND / "requirements.lock")
    assert {"langgraph", "langgraph-checkpoint-sqlite"} <= direct
    assert {"langgraph", "langgraph-checkpoint-sqlite", "aiosqlite"} <= locked
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_supply_chain_audit.py -q
```

Expected: direct dependency assertion fails.

- [ ] **Step 3: Add pinned dependencies and regenerate lock**

Append:

```text
langgraph==1.2.6
langgraph-checkpoint-sqlite==3.1.0
```

Then run:

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -m pip install -r backend/requirements.txt
"$PYTHON_BIN" -m pip freeze > backend/requirements.lock
```

- [ ] **Step 4: Verify GREEN and imports**

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -c 'from langgraph.graph import StateGraph; from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver'
"$PYTHON_BIN" -m pytest tests/test_supply_chain_audit.py -q
```

Expected: imports and audit tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/requirements.lock tests/test_supply_chain_audit.py
git commit -m "build: add LangGraph checkpoint dependencies"
```

### Task 2: Define checkpoint-safe graph state and reducers

**Files:**
- Create: `backend/workflow_state.py`
- Modify: `backend/agent_state.py`
- Test: `tests/test_workflow_state.py`

- [ ] **Step 1: Write failing state and reducer tests**

```python
import json

from state_memory import initialize_agent_state
from workflow_state import (
    agent_state_from_graph,
    agent_state_to_graph,
    append_unique,
    merge_dicts,
    rag_index_from_payload,
    rag_index_to_payload,
)


def test_agent_state_graph_round_trip_is_json_serializable():
    domain = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="run-1")
    graph = agent_state_to_graph(domain, pipeline_id="v1")
    json.dumps(graph, ensure_ascii=False)
    restored = agent_state_from_graph(graph)
    assert restored.model_dump(mode="json") == domain.model_dump(mode="json")


def test_reducers_merge_parallel_agent_deltas_without_aliasing():
    left = {"1": {"markdown": "a"}}
    right = {"2": {"markdown": "b"}}
    merged = merge_dicts(left, right)
    right["2"]["markdown"] = "changed"
    assert set(merged) == {"1", "2"}
    assert merged["2"]["markdown"] == "b"


def test_append_unique_deduplicates_stable_ids():
    assert append_unique([{"id": "x"}], [{"id": "x"}, {"id": "y"}]) == [{"id": "x"}, {"id": "y"}]


def test_rag_index_payload_round_trip_preserves_searchable_chunks():
    index = InMemoryRagIndex([RagChunk("c1", "filing", "revenue grew", {"page": 1}, [1.0, 0.0])])
    restored = rag_index_from_payload(rag_index_to_payload(index))
    assert restored.chunks[0].text == "revenue grew"
    assert restored.has_embeddings is True
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_state.py -q
```

Expected: missing `workflow_state`.

- [ ] **Step 3: Implement reducer functions**

Use pure deep-copying reducers:

```python
def merge_dicts(left: dict | None, right: dict | None) -> dict:
    merged = copy.deepcopy(left or {})
    merged.update(copy.deepcopy(right or {}))
    return merged


def append_unique(left: list | None, right: list | None) -> list:
    result = copy.deepcopy(left or [])
    seen = {json.dumps(item, sort_keys=True, ensure_ascii=False, default=str) for item in result}
    for item in copy.deepcopy(right or []):
        marker = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            result.append(item)
            seen.add(marker)
    return result
```

- [ ] **Step 4: Define AgentGraphState**

Create the TypedDict with `total=False` and explicit reducers:

```python
class AgentGraphState(TypedDict, total=False):
    run_id: str
    ticker: str
    company_name: str
    pipeline_id: str
    raw_financial_data: dict[str, dict[str, Any]]
    provider_values: dict[str, list[dict[str, Any]]]
    normalized_financials: dict[str, Any]
    source_audit: Annotated[list[dict[str, Any]], append_unique]
    validation_issues: list[dict[str, Any]]
    circuit_breaker: dict[str, Any]
    peer_context: dict[str, Any]
    quant_metrics: dict[str, Any]
    tool_results: Annotated[dict[str, Any], merge_dicts]
    agent_reports: Annotated[dict[str, dict[str, Any]], merge_dicts]
    risk_flags: Annotated[list[dict[str, Any]], append_unique]
    execution_trace: Annotated[list[dict[str, Any]], append_unique]
    analyses: Annotated[dict[str, str], merge_dicts]
    structured_outputs: Annotated[dict[str, dict[str, Any]], merge_dicts]
    blocking_issues: Annotated[list[str], append_unique]
    final_audit: dict[str, Any]
    report_filename: str
    report_event: dict[str, Any]
    started_at: float
    total_time: float
    status: str
    retryable_error: dict[str, Any] | None
```

Do not put callbacks, clients, locks, compiled graphs, rotators, or `InMemoryRagIndex` objects in this schema.

- [ ] **Step 5: Implement domain and RAG adapters**

`agent_state_to_graph()` uses `model_dump(mode="json")`; `agent_state_from_graph()` passes only `AgentState.model_fields` to `AgentState.model_validate()`. Store serialized RAG under `tool_results["rag_index"]`; rebuild `InMemoryRagIndex` only in the ephemeral compatibility context.

- [ ] **Step 6: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_state.py tests/test_agent_state_memory.py -q
```

Expected: graph and existing domain-state tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/workflow_state.py backend/agent_state.py tests/test_workflow_state.py
git commit -m "feat: add checkpoint-safe agent graph state"
```

### Task 3: Build conditional validation and repair topology

**Files:**
- Create: `backend/workflow_graph.py`
- Test: `tests/test_workflow_graph_routing.py`

- [ ] **Step 1: Write failing route tests with fake services**

Compile with `InMemorySaver` and fake nodes that append stable trace entries:

```python
def test_closed_validation_skips_repair():
    services = FakeWorkflowServices(validation_statuses=["closed"])
    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))
    assert services.calls[:2] == ["validate", "agent:22"]
    assert "repair" not in services.calls


def test_open_validation_repairs_then_runs_agents():
    services = FakeWorkflowServices(validation_statuses=["open", "closed"])
    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))
    assert services.calls[:3] == ["validate", "repair", "validate"]
    assert result["status"] == "done"


def test_open_after_repair_blocks_all_agents():
    services = FakeWorkflowServices(validation_statuses=["open", "open"])
    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))
    assert not any(call.startswith("agent:") for call in services.calls)
    assert result["status"] == "blocked"


def test_v1_builds_one_node_per_configured_agent_and_parallel_joins():
    builder = build_analysis_graph_builder("v1", FakeWorkflowServices())
    graph = builder.compile()
    node_names = set(graph.get_graph().nodes)
    assert {f"agent_{number}" for number in (11, 1, 2, 3, 20, 4, 5, 6, 21, 7)} <= node_names
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_graph_routing.py -q
```

Expected: missing `workflow_graph`.

- [ ] **Step 3: Define WorkflowServices**

Use a frozen dataclass containing callables rather than concrete globals:

```python
@dataclass(frozen=True)
class WorkflowServices:
    initialize: Callable[[dict, str], AgentGraphState]
    validate: Callable[[AgentGraphState], AgentGraphState]
    repair: Callable[[AgentGraphState], Awaitable[AgentGraphState]]
    prepare: Callable[[AgentGraphState], Awaitable[dict]]
    run_agent: Callable[[int, AgentGraphState], Awaitable[dict]]
    final_audit: Callable[[AgentGraphState], Awaitable[dict]]
    tear_sheet: Callable[[AgentGraphState], Awaitable[dict]]
    persist_report: Callable[[AgentGraphState], Awaitable[dict]]
    progress_callback: Callable | None = None
    cancel_check: Callable[[], None] | None = None
```

Production factory functions may capture process-local clients. The state never captures them.

- [ ] **Step 4: Implement routing functions and fixed nodes**

Use pure route functions:

```python
def route_after_validation(state: AgentGraphState) -> Literal["repair_data", "prepare_analysis"]:
    return "repair_data" if state.get("circuit_breaker", {}).get("status") == "open" else "prepare_analysis"


def route_after_repair_validation(state: AgentGraphState) -> Literal["blocked_finalize", "prepare_analysis"]:
    return "blocked_finalize" if state.get("circuit_breaker", {}).get("status") == "open" else "prepare_analysis"
```

Add `START -> initialize -> validate_data`; conditional edges as specified; blocked finalize goes directly to `END`.

- [ ] **Step 5: Build configured Agent nodes and barriers**

For each `pipeline_def["agents"]`, add exactly one `agent_{number}` node. Connect `prepare_analysis` to every node in the first group. After every group, add a no-op `group_{index}_join` node and connect with `builder.add_edge(list(group_node_names), join_name)`. Connect that join node to every Agent in the next group. This exact list-source edge is the barrier: the join node runs once only after every node in that group has finished.

After the last group, connect its join node to `final_audit -> tear_sheet -> persist_report -> finalize -> END`. `persist_report` receives `AGENT_RETRY_POLICY`; `finalize` is a pure state/status update.

- [ ] **Step 6: Add retry policy only to external nodes**

```python
def is_retryable_workflow_error(exc: BaseException) -> bool:
    return isinstance(exc, (AgentRateLimitError, AgentTransientError, AgentServerError, TimeoutError, ConnectionError))


AGENT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    initial_interval=2.0,
    backoff_factor=2.0,
    max_interval=30.0,
    jitter=True,
    retry_on=is_retryable_workflow_error,
)
```

Apply it to repair, prepare/RAG, Agent, final audit, tear-sheet, and idempotent report-persistence nodes; do not apply it to pure validation, routing, join, or finalize nodes.

- [ ] **Step 7: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_graph_routing.py -q
```

Expected: all conditional path and topology assertions pass.

- [ ] **Step 8: Commit**

```bash
git add backend/workflow_graph.py tests/test_workflow_graph_routing.py
git commit -m "feat: build conditional LangGraph workflow"
```

### Task 4: Adapt existing analysis engines into isolated graph nodes

**Files:**
- Modify: `backend/workflow_graph.py`
- Modify: `backend/agent_runtime/pipeline_runner.py`
- Test: `tests/test_workflow_agent_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Patch `run_agent_with_quality_gates_async` and prove an Agent node receives previous-group analyses but returns only its own delta:

```python
def test_agent_node_rebuilds_legacy_context_and_returns_isolated_delta(monkeypatch):
    seen = {}

    async def fake_run(agent_num, data, context, rotator, progress):
        seen.update(context)
        context.setdefault("structured_outputs", {})[agent_num] = {"score": 8}
        return agent_num, f"agent-{agent_num}"

    services = create_default_workflow_services(rotator=FakeRotator(), progress_callback=None)
    result = asyncio.run(services.run_agent(2, state_with_analysis("1", "previous")))

    assert seen["analyses"]["1"] == "previous"
    assert result["analyses"] == {"2": "agent-2"}
    assert result["structured_outputs"] == {"2": {"score": 8}}
    assert set(result["agent_reports"]) == {"2"}
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_agent_adapter.py -q
```

Expected: default production services do not exist.

- [ ] **Step 3: Implement compatibility context reconstruction**

Create `legacy_context_from_graph(state, services)` that deep-copies data, analyses, structured outputs, state-derived Pydantic `agent_state`, pipeline metadata, and reconstructed RAG index. Attach progress/cancel callbacks only to this ephemeral dict.

Do not write the context back wholesale. `agent_node` extracts and returns only:

- its own `analyses` entry;
- its own structured output;
- the corresponding serialized `AgentReport`;
- new risk flags and trace entries;
- blocking issues introduced during this call.

- [ ] **Step 4: Implement prepare, audit, and tear-sheet adapters**

`prepare_analysis` serializes RAG chunks to `tool_results["rag_index"]`. `final_audit` reconstructs context and calls `finalize_final_audit_async`; `tear_sheet` calls `ensure_tear_sheet_summary_async`. `persist_report` renders and saves through the injected `ReportStorage`, using the checkpointed deterministic `report_filename`, and returns `report_event`. These nodes return only changed serializable fields. Repeating `persist_report` after a crash atomically overwrites the same keys and idempotently upserts metadata.

- [ ] **Step 5: Change AnalysisPipelineRunner to the graph**

Extend `AnalysisRequest` with optional `thread_id` and `checkpointer`. `AnalysisPipelineRunner.run_async` calls `run_analysis_workflow(...)` and wraps the final graph state in the current `AnalysisResult`, preserving `context`, `pipeline_id`, timing, and warning contracts.

Default direct/CLI calls use `InMemorySaver`; Worker calls provide SQLite persistence.

- [ ] **Step 6: Verify focused compatibility**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_agent_adapter.py tests/test_architecture_services.py tests/test_dual_pipeline_job.py tests/test_v4_pipeline_mode.py -q
```

Expected: adapter and existing runner contracts pass without external LLM calls.

- [ ] **Step 7: Commit**

```bash
git add backend/workflow_graph.py backend/agent_runtime/pipeline_runner.py backend/agent_runtime/types.py tests/test_workflow_agent_adapter.py
git commit -m "refactor: run analysis engines as graph nodes"
```

### Task 5: Add SQLite checkpoint lifecycle and 429 resume

**Files:**
- Modify: `backend/workflow_graph.py`
- Modify: `backend/analysis_jobs.py`
- Modify: `backend/job_store.py`
- Test: `tests/test_workflow_checkpoint_resume.py`

- [ ] **Step 1: Write a real SQLite resume test**

Use a temporary DB and a deterministic two-node graph. Node A increments a counter and succeeds; node B raises `AgentRateLimitError` on its first invocation and succeeds after a flag changes:

```python
def test_sqlite_resume_does_not_repeat_successful_nodes(tmp_path):
    calls = {"a": 0, "b": 0}
    checkpoint = tmp_path / "checkpoints.sqlite3"
    thread_id = "job-429"

    with pytest.raises(AgentRateLimitError):
        asyncio.run(run_resume_fixture(checkpoint, thread_id, calls, allow_b=False))

    result = asyncio.run(run_resume_fixture(checkpoint, thread_id, calls, allow_b=True, resume=True))

    assert result["status"] == "done"
    assert calls == {"a": 1, "b": 2}
```

Also assert `PRAGMA journal_mode` is `wal` and `busy_timeout` is 30000 on the created DB.

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_checkpoint_resume.py -q
```

Expected: no SQLite workflow executor exists.

- [ ] **Step 3: Implement checkpointer context manager**

```python
@asynccontextmanager
async def open_sqlite_checkpointer(path: str | Path):
    target = Path(path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(target)) as saver:
        await saver.conn.execute("PRAGMA journal_mode=WAL")
        await saver.conn.execute("PRAGMA busy_timeout=30000")
        await saver.conn.execute("PRAGMA synchronous=NORMAL")
        await saver.setup()
        yield saver
```

Never keep this connection in module globals or create it before multiprocessing spawn.

- [ ] **Step 4: Implement initial-vs-resume execution**

```python
async def execute_persistent_workflow(*, initial_state, pipeline_id, thread_id, checkpoint_path, services):
    config = {"configurable": {"thread_id": thread_id}}
    async with open_sqlite_checkpointer(checkpoint_path) as saver:
        graph = build_analysis_graph_builder(pipeline_id, services).compile(checkpointer=saver)
        snapshot = await graph.aget_state(config)
        if snapshot.values and not snapshot.next:
            return dict(snapshot.values)
        graph_input = None if snapshot.values else initial_state
        return await graph.ainvoke(graph_input, config=config)
```

Do not use `Command(resume=...)` for error recovery; that API is for explicit `interrupt()`. Failure recovery uses `None` and the same `thread_id`.

- [ ] **Step 5: Wire stable job IDs and retry status**

Pass `thread_id=f"{job_id}:{current_pipeline_id}"` from `analysis_jobs.py`, so a multi-pipeline run has one independent graph thread per pipeline. Generate `report_filename` deterministically from `job_id` and `current_pipeline_id` before the initial invoke and keep it in graph state. Replace the old post-run `render_and_persist_report()` call with the checkpointed `report_event`; a completed pipeline therefore does not emit a duplicate report when a later pipeline makes the outer RQ job retry. On `AgentRateLimitError`, update the job to `waiting_retry`, append an event containing `thread_id` and retry category, then re-raise for RQ. On the next RQ attempt, return to `running` and invoke with the same thread id.

Do not mark a retryable error terminal in the broad exception handler.

- [ ] **Step 6: Verify GREEN and red-green integrity**

Run the test once with resume logic temporarily disabled and confirm node A count becomes 2; restore resume logic and rerun:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_workflow_checkpoint_resume.py -q
```

Expected after restore: all resume tests pass and successful node count remains 1.

- [ ] **Step 7: Commit**

```bash
git add backend/workflow_graph.py backend/analysis_jobs.py backend/job_store.py tests/test_workflow_checkpoint_resume.py
git commit -m "feat: resume rate-limited workflows from checkpoints"
```

### Task 6: Remove production DAG orchestration and preserve imports

**Files:**
- Modify: `backend/pipeline_async.py`
- Modify: `backend/pipeline.py`
- Modify: `backend/agent_runtime/pipeline_compat.py`
- Modify: `tests/test_import_boundaries.py`
- Modify: `tests/test_data_cross_validator.py`
- Test: `tests/test_no_legacy_dag_runner.py`

- [ ] **Step 1: Write a failing source-boundary test**

```python
def test_production_pipeline_has_no_manual_dag_group_runner():
    source = (BACKEND / "pipeline_async.py").read_text(encoding="utf-8")
    assert "_run_agent_groups" not in source
    assert "asyncio.as_completed" not in source
    assert "pipeline_def[\"groups\"]" not in source
    assert "run_analysis_workflow" in source
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_no_legacy_dag_runner.py -q
```

Expected: old DAG loop markers are present.

- [ ] **Step 3: Replace pipeline_async with a thin wrapper**

The module retains `run_analysis_pipeline_async(data, progress_callback=None, pipeline_id="v1", cancel_check=None, thread_id=None, checkpointer=None)` for callers, builds an `AnalysisRequest`, calls `AnalysisPipelineRunner`, and returns `.context`. It contains no node/group orchestration.

Update tests that imported private `_initialize_agent_state_context` or `_run_agent_groups` to test validation and graph routing through public workflow functions.

- [ ] **Step 4: Prevent circular imports**

Make `pipeline.py` a compatibility export that imports the graph-backed async wrapper lazily. `AnalysisPipelineRunner` must import `workflow_graph`, never `pipeline.py`. `pipeline_compat.py` delegates to the canonical runner.

- [ ] **Step 5: Verify GREEN and pipeline regressions**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_no_legacy_dag_runner.py tests/test_data_cross_validator.py tests/test_dual_pipeline_job.py tests/test_v4_pipeline_mode.py tests/test_import_boundaries.py -q
```

Expected: source boundary, validation, smoke, and import boundary tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline_async.py backend/pipeline.py backend/agent_runtime/pipeline_compat.py tests/test_no_legacy_dag_runner.py tests/test_data_cross_validator.py tests/test_import_boundaries.py
git commit -m "refactor: retire manual DAG orchestration"
```

### Task 7: Architecture documentation and full verification

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/operator-guide.md`
- Modify: `README.md`
- Test: full suite

- [ ] **Step 1: Update Runtime Flow**

Replace the DAG runner diagram with API → Redis/RQ → persistent StateGraph. Show validation conditional edges, repair/blocked routes, parallel Agent super-steps, SQLite checkpoints, report storage, and job-event polling.

Document:

- `job_id:pipeline_id` thread naming;
- `None` + same thread id error recovery;
- checkpoint backup and deletion policy;
- state serialization restrictions;
- difference between short LangGraph node retry and delayed RQ retry.

- [ ] **Step 2: Run focused graph suite**

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -m pytest tests/test_workflow_state.py tests/test_workflow_graph_routing.py tests/test_workflow_agent_adapter.py tests/test_workflow_checkpoint_resume.py tests/test_no_legacy_dag_runner.py -q
```

Expected: focused graph suite passes.

- [ ] **Step 3: Run full verification**

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" scripts/check_runtime.py
"$PYTHON_BIN" -m compileall -q backend main.py
git diff --check
```

Expected: every command exits 0 and diff check is silent.

- [ ] **Step 4: Commit**

```bash
git add docs/architecture.md docs/operator-guide.md README.md
git commit -m "docs: document durable LangGraph runtime"
```
