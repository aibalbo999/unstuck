import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import api  # noqa: E402
import job_store  # noqa: E402
from state_memory import initialize_agent_state  # noqa: E402
from workflow_graph import run_analysis_workflow  # noqa: E402
from workflow_state import agent_state_to_graph  # noqa: E402


class TelemetryWorkflowServices:
    def __init__(self, *, fail_agent=False):
        self.fail_agent = fail_agent
        self.progress_callback = None
        self.cancel_check = None
        self.telemetry_callback = lambda payload: self.records.append(payload)
        self.records = []

    def initialize(self, data, pipeline_id):
        domain = initialize_agent_state(data, run_id="telemetry-job")
        return agent_state_to_graph(domain, pipeline_id=pipeline_id)

    def validate(self, _state):
        return {"circuit_breaker": {"status": "closed"}, "validation_issues": []}

    async def repair(self, _state):
        return {}

    async def prepare(self, _state):
        return {}

    async def run_agent(self, agent_num, _state):
        if self.fail_agent:
            raise RuntimeError("provider token=sk-live-secret should be hidden")
        return {"analyses": {str(agent_num): f"agent-{agent_num}"}}

    async def final_audit(self, _state):
        return {"final_audit": {"status": "passed"}}

    async def chief_editor(self, _state):
        return {"executive_thesis": "ok"}

    async def tear_sheet(self, _state):
        return {}

    async def persist_report(self, _state):
        return {}


def test_langgraph_success_node_writes_telemetry_callback_payload():
    services = TelemetryWorkflowServices()
    initial_state = services.initialize({"ticker": "2330.TW", "company_name": "台積電"}, "v4")

    asyncio.run(run_analysis_workflow(initial_state=initial_state, pipeline_id="v4", services=services))

    node_names = {record["node_name"] for record in services.records}
    assert {"initialize", "validate_data", "prepare_analysis", "agent_22", "finalize"} <= node_names
    agent_record = next(record for record in services.records if record["node_name"] == "agent_22")
    assert agent_record["status"] == "success"
    assert agent_record["latency_ms"] >= 0
    assert agent_record["input_tokens"] is None
    assert agent_record["output_tokens"] is None
    assert agent_record["quality_gate_pass"] is True


def test_langgraph_failed_node_writes_sanitized_telemetry_before_reraising():
    services = TelemetryWorkflowServices(fail_agent=True)
    initial_state = services.initialize({"ticker": "2330.TW", "company_name": "台積電"}, "v4")

    with pytest.raises(RuntimeError):
        asyncio.run(run_analysis_workflow(initial_state=initial_state, pipeline_id="v4", services=services))

    failed = next(record for record in services.records if record["node_name"] == "agent_22")
    assert failed["status"] == "failed"
    assert "RuntimeError" in failed["error"]
    assert "sk-live-secret" not in failed["error"]
    assert "[redacted]" in failed["error"]


def test_telemetry_store_schema_is_stable_and_api_sanitizes_secret():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.record_node_telemetry(
        {
            "job_id": job_id,
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "node_name": "valuation_agent",
            "model": "model-a",
            "started_at": 10.0,
            "finished_at": 12.5,
            "latency_ms": 2500,
            "status": "failed",
            "retry_count": 1,
            "input_tokens": None,
            "output_tokens": None,
            "cache_hit": False,
            "quality_gate_pass": False,
            "error": "ValueError: API_KEY=super-secret-token",
        }
    )

    client = TestClient(api.app)
    response = client.get(f"/api/analysis-jobs/{job_id}/telemetry")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    assert set(body["telemetry"][0]) == {
        "id",
        "job_id",
        "ticker",
        "pipeline_id",
        "node_name",
        "model",
        "started_at",
        "finished_at",
        "latency_ms",
        "status",
        "retry_count",
        "input_tokens",
        "output_tokens",
        "cache_hit",
        "quality_gate_pass",
        "error",
    }
    assert body["telemetry"][0]["error"] == "ValueError: API_KEY=[redacted]"
    assert "super-secret-token" not in response.text
