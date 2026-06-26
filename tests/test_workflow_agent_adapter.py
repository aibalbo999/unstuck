import asyncio
import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from state_memory import initialize_agent_state
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from workflow_graph import create_default_workflow_services, legacy_context_from_graph
from workflow_state import agent_state_to_graph


class FakeRotator:
    pass


def state_with_analysis(agent_id="1", markdown="previous", *, pipeline_id="v1"):
    domain = initialize_agent_state(
        {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
        run_id="run-adapter",
    )
    graph = agent_state_to_graph(domain, pipeline_id=pipeline_id)
    graph["analyses"] = {str(agent_id): markdown}
    graph["structured_outputs"] = {str(agent_id): {"score": 7}}
    graph["blocking_issues"] = ["pre-existing warning"]
    return graph


def test_legacy_context_from_graph_rebuilds_runtime_only_objects():
    services = create_default_workflow_services(rotator=FakeRotator(), progress_callback=None)
    state = state_with_analysis("1", "previous")

    context = legacy_context_from_graph(state, services)

    assert context["ticker"] == "2330.TW"
    assert context["company_name"] == "台積電"
    assert context["pipeline_id"] == "v1"
    assert context["analyses"][1] == "previous"
    assert context["structured_outputs"][1] == {"score": 7}
    assert context["agent_state"].ticker == "2330.TW"
    assert "rag_index" not in state


def test_agent_node_rebuilds_legacy_context_and_returns_isolated_delta(monkeypatch):
    seen = {}

    async def fake_run(agent_num, data, context, rotator, progress_callback=None):
        seen["data"] = copy.deepcopy(data)
        seen["context"] = copy.deepcopy({k: v for k, v in context.items() if k != "agent_state"})
        seen["rotator"] = rotator
        seen["progress_callback"] = progress_callback
        context.setdefault("structured_outputs", {})[agent_num] = {"score": 8}
        context.setdefault("analyses", {})[agent_num] = f"agent-{agent_num}"
        context.setdefault("blocking_issues", []).append(f"agent-{agent_num} warning")
        return agent_num, f"agent-{agent_num}"

    monkeypatch.setattr("workflow_services.run_agent_with_quality_gates_async", fake_run)
    services = create_default_workflow_services(rotator=FakeRotator(), progress_callback="progress")

    result = asyncio.run(services.run_agent(2, state_with_analysis("1", "previous")))

    assert seen["data"]["ticker"] == "2330.TW"
    assert seen["context"]["analyses"][1] == "previous"
    assert seen["context"]["structured_outputs"][1] == {"score": 7}
    assert seen["rotator"].__class__ is FakeRotator
    assert seen["progress_callback"] == "progress"
    assert result["analyses"] == {"2": "agent-2"}
    assert result["structured_outputs"] == {"2": {"score": 8}}
    assert set(result["agent_reports"]) == {"2"}
    assert result["agent_reports"]["2"]["markdown"] == "agent-2"
    assert result["blocking_issues"] == ["agent-2 warning"]


def test_analysis_pipeline_runner_invokes_langgraph_and_preserves_result_contract(monkeypatch):
    import agent_runtime.pipeline_runner as pipeline_runner

    calls = {}
    checkpointer = object()

    class FakeServices:
        def __init__(self):
            self.progress_callback = None
            self.cancel_check = None

        def initialize(self, data, pipeline_id):
            domain = initialize_agent_state(data, run_id="run-runner")
            return agent_state_to_graph(domain, pipeline_id=pipeline_id)

    fake_services = FakeServices()

    def fake_create_services(*, progress_callback=None, cancel_check=None):
        fake_services.progress_callback = progress_callback
        fake_services.cancel_check = cancel_check
        return fake_services

    async def fake_run_workflow(*, initial_state, pipeline_id, services, checkpointer=None, thread_id=None):
        calls.update(
            initial_state=initial_state,
            pipeline_id=pipeline_id,
            services=services,
            checkpointer=checkpointer,
            thread_id=thread_id,
        )
        final_state = dict(initial_state)
        final_state.update(
            {
                "pipeline_id": pipeline_id,
                "analyses": {"22": "agent-22"},
                "structured_outputs": {"22": {"score": 9}},
                "blocking_issues": ["non-terminal warning"],
                "status": "done",
                "total_time": 1.25,
            }
        )
        return final_state

    async def old_pipeline_should_not_run(*_args, **_kwargs):
        raise AssertionError("runner should call LangGraph workflow, not pipeline_async")

    monkeypatch.setattr(pipeline_runner, "create_default_workflow_services", fake_create_services, raising=False)
    monkeypatch.setattr(pipeline_runner, "run_analysis_workflow", fake_run_workflow, raising=False)
    monkeypatch.setattr("pipeline.run_analysis_pipeline_async", old_pipeline_should_not_run)

    result = asyncio.run(
        AnalysisPipelineRunner().run_async(
            AnalysisRequest(
                data={"ticker": "2330.TW", "company_name": "台積電"},
                pipeline_id="v4",
                progress_callback="progress",
                cancel_check=lambda: None,
                thread_id="job-1:v4",
                checkpointer=checkpointer,
            )
        )
    )

    assert calls["pipeline_id"] == "v4"
    assert calls["services"] is fake_services
    assert calls["checkpointer"] is checkpointer
    assert calls["thread_id"] == "job-1:v4"
    assert result.pipeline_id == "v4"
    assert result.context["analyses"][22] == "agent-22"
    assert result.context["structured_outputs"][22] == {"score": 9}
    assert result.warnings == ["non-terminal warning"]
