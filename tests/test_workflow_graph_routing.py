import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from langgraph.checkpoint.memory import InMemorySaver

from pipeline_modes import get_pipeline_definition
from state_memory import initialize_agent_state
from workflow_graph import build_analysis_graph_builder, route_after_final_audit, route_after_validation, run_analysis_workflow
from workflow_state import agent_state_to_graph


class FakeWorkflowServices:
    def __init__(self, *, validation_statuses=None, final_audit_delta=None):
        self.validation_statuses = list(validation_statuses or ["closed"])
        self.final_audit_delta = final_audit_delta
        self.validation_count = 0
        self.calls: list[str] = []
        self.agent_states: dict[int, dict] = {}

    def initialize(self, data, pipeline_id):
        domain = initialize_agent_state(data, run_id="run-graph-routing")
        return agent_state_to_graph(domain, pipeline_id=pipeline_id)

    def validate(self, state):
        self.calls.append("validate")
        index = min(self.validation_count, len(self.validation_statuses) - 1)
        self.validation_count += 1
        status = self.validation_statuses[index]
        return {
            "circuit_breaker": {
                "status": status,
                "blocking_fields": ["total_debt"] if status == "open" else [],
                "attempts": self.validation_count,
                "reason": "fake validation",
            },
            "validation_issues": [
                {
                    "field": "total_debt",
                    "severity": "critical",
                    "providers": ["a", "b"],
                }
            ]
            if status == "open"
            else [],
        }

    async def repair(self, state):
        self.calls.append("repair")
        return {"execution_trace": [{"id": "repair", "node": "repair_data"}]}

    async def prepare(self, state):
        return {"execution_trace": [{"id": "prepare", "node": "prepare_analysis"}]}

    async def run_agent(self, agent_num, state):
        self.calls.append(f"agent:{agent_num}")
        self.agent_states[agent_num] = dict(state)
        return {
            "analyses": {str(agent_num): f"agent-{agent_num}"},
            "agent_reports": {
                str(agent_num): {
                    "agent_id": str(agent_num),
                    "role": f"agent-{agent_num}",
                    "markdown": f"agent-{agent_num}",
                    "extracted_facts": {},
                    "structured_output": None,
                    "risk_flags": [],
                    "citations": [],
                    "token_usage": {},
                }
            },
        }

    async def final_audit(self, state):
        self.calls.append("final_audit")
        if self.final_audit_delta is not None:
            return self.final_audit_delta
        return {"final_audit": {"ok": True}}

    async def tear_sheet(self, state):
        self.calls.append("tear_sheet")
        return {"structured_outputs": {"tear_sheet": {"ok": True}}}

    async def persist_report(self, state):
        self.calls.append("persist_report")
        return {"report_event": {"filename": "fake.md"}}


async def run_fake_graph(services, *, pipeline_id="v4"):
    initial_state = services.initialize(
        {"ticker": "2330.TW", "company_name": "台積電"},
        pipeline_id,
    )
    return await run_analysis_workflow(
        initial_state=initial_state,
        pipeline_id=pipeline_id,
        services=services,
        checkpointer=InMemorySaver(),
        thread_id="routing-test",
    )


def test_closed_validation_skips_repair():
    services = FakeWorkflowServices(validation_statuses=["closed"])

    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))

    assert services.calls[:2] == ["validate", "agent:22"]
    assert "repair" not in services.calls
    assert result["status"] == "done"


def test_open_validation_repairs_then_runs_agents():
    services = FakeWorkflowServices(validation_statuses=["open", "closed"])

    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))

    assert services.calls[:3] == ["validate", "repair", "validate"]
    assert any(call.startswith("agent:") for call in services.calls)
    assert result["status"] == "done"


def test_open_after_repair_blocks_all_agents():
    services = FakeWorkflowServices(validation_statuses=["open", "open"])

    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))

    assert services.calls == ["validate", "repair", "validate"]
    assert not any(call.startswith("agent:") for call in services.calls)
    assert result["status"] == "blocked"
    assert result["blocking_issues"]


def test_route_after_validation_repairs_when_circuit_breaker_is_open():
    assert route_after_validation({"circuit_breaker": {"status": "open"}}) == "repair_data"


def test_route_after_final_audit_blocks_when_blocking_issues_are_present():
    assert route_after_final_audit({"blocking_issues": ["final_audit:critical_gap"]}) == "blocked_finalize"


def test_final_audit_repair_limit_blocks_before_tear_sheet_and_persist():
    services = FakeWorkflowServices(
        validation_statuses=["closed"],
        final_audit_delta={
            "status": "blocked",
            "repair_iteration_count": 2,
            "blocking_issues": ["final_audit:repair_iteration_limit"],
            "audit_repair_log": ["部分審計修復未完成"],
            "final_audit": {"status": "needs_attention", "critical": ["still broken"]},
        },
    )

    result = asyncio.run(run_fake_graph(services, pipeline_id="v4"))

    assert result["status"] == "blocked"
    assert result["repair_iteration_count"] == 2
    assert "final_audit:repair_iteration_limit" in result["blocking_issues"]
    assert "tear_sheet" not in services.calls
    assert "persist_report" not in services.calls


def test_v1_builds_one_node_per_configured_agent_and_parallel_joins():
    graph = build_analysis_graph_builder("v1", FakeWorkflowServices()).compile()

    node_names = set(graph.get_graph().nodes)

    assert {f"agent_{number}" for number in (11, 1, 2, 3, 20, 4, 5, 6, 21, 7)} <= node_names
    assert {"agent_4_preload", "agent_5_preload"} <= node_names
    assert {"group_3_join", "group_4_join"} <= node_names


def test_v1_groups_parallelize_independent_agents_without_changing_sequence():
    definition = get_pipeline_definition("v1")

    assert definition["agents"] == (11, 1, 2, 3, 20, 4, 5, 6, 21, 7)
    assert (1, 2) in definition["groups"]
    assert (6, 21) in definition["groups"]
    assert definition["preload_after_groups"] == {2: (4, 5)}


def test_v1_preloads_quant_context_before_valuation_and_growth_agents_run():
    services = FakeWorkflowServices(validation_statuses=["closed"])

    result = asyncio.run(run_fake_graph(services, pipeline_id="v1"))

    assert "agent_4_preload" in result["tool_results"]
    assert "agent_5_preload" in result["tool_results"]
    assert "agent_4_preload" in services.agent_states[4]["tool_results"]
    assert "agent_5_preload" in services.agent_states[5]["tool_results"]
    assert result["tool_results"]["agent_4_preload"]["agent_num"] == 4
    assert result["tool_results"]["agent_5_preload"]["agent_num"] == 5
