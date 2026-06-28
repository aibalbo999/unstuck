import asyncio
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from state_memory import initialize_agent_state
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
import agent_runtime.quality_gates as quality_gates
import pipeline_sync
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
        context.setdefault("agent_quality_retry_counts", {})[agent_num] = 1
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
    assert result["agent_quality_retry_counts"] == {"2": 1}
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


def test_quality_gates_retries_once_when_structured_output_parse_fails(monkeypatch):
    calls = []
    statuses = []
    valid_valuation = json.dumps(
        {
            "price_targets": {
                "dcf_reasoning": "normalized FCF 搭配市場價值 WACC。",
                "peer_reasoning": "同業倍數只作交叉檢查。",
                "scenario_reasoning": "熊市折讓需求下修，牛市反映產能開出。",
                "熊市情境": 80,
                "基本情境": 100,
                "牛市情境": 120,
            },
            "valuation_summary": {
                "primary_method": "blended",
                "uses_market_value_wacc": True,
                "uses_normalized_fcf": True,
                "double_counting_check": "未重複計價。",
            },
            "analysis_markdown": "估值正文",
        },
        ensure_ascii=False,
    )

    async def fake_run_single_agent_async(agent_num, data, context, rotator):
        calls.append(agent_num)
        return "不是 JSON" if len(calls) == 1 else valid_valuation

    async def fake_emit_status_async(progress_callback, message, **kwargs):
        statuses.append((message, kwargs))

    async def noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr(quality_gates, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(quality_gates, "emit_status_async", fake_emit_status_async)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop_async)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop_async)
    context = {
        "pipeline_id": "v1",
        "pipeline_label": "Mode A",
        "agent_positions": {4: 4},
        "agent_total": 10,
        "agent_sequence": (11, 1, 2, 3, 20, 4, 5, 6, 21, 7),
        "structured_outputs": {},
        "analyses": {},
        "data": {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
    }

    completed_agent, markdown = asyncio.run(
        quality_gates.run_agent_with_quality_gates_async(
            4,
            context["data"],
            context,
            FakeRotator(),
        )
    )

    assert completed_agent == 4
    assert len(calls) == 2
    assert context["structured_outputs"][4]["price_targets"]["基本情境"] == 100
    assert context["analyses"][4] == markdown
    retry_events = [item for item in statuses if item[1].get("phase") == "structured_retry"]
    assert len(retry_events) == 1


def test_quality_gates_retries_once_when_financial_redline_fails(monkeypatch):
    calls = []
    retry_instructions = []
    statuses = []
    bad_financial_output = (
        "## 財務分析\n"
        "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。"
    )
    clean_financial_output = "## 財務分析\n採用同期間年度杜邦恒等式；若資料口徑不同，僅列資料品質警示。"

    async def fake_run_single_agent_async(agent_num, data, context, rotator):
        calls.append(agent_num)
        retry_instructions.append(str(context.get("_audit_retry_instruction") or ""))
        return bad_financial_output if len(calls) == 1 else clean_financial_output

    async def fake_emit_status_async(progress_callback, message, **kwargs):
        statuses.append((message, kwargs))

    async def noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr(quality_gates, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(quality_gates, "emit_status_async", fake_emit_status_async)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop_async)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop_async)

    context = {
        "pipeline_id": "v1",
        "pipeline_label": "Mode A",
        "agent_positions": {2: 2},
        "agent_total": 10,
        "agent_sequence": (11, 1, 2, 3, 20, 4, 5, 6, 21, 7),
        "structured_outputs": {},
        "analyses": {},
        "data": {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
    }

    completed_agent, markdown = asyncio.run(
        quality_gates.run_agent_with_quality_gates_async(
            2,
            context["data"],
            context,
            FakeRotator(),
        )
    )

    assert completed_agent == 2
    assert len(calls) == 2
    assert retry_instructions[0] == ""
    assert "杜邦分析紅線" in retry_instructions[1]
    assert context.get("_audit_retry_instruction") is None
    assert context["agent_quality_retry_counts"] == {2: 1}
    assert context["analyses"][2] == markdown == clean_financial_output
    assert "系統品質檢查警示" not in markdown
    retry_events = [item for item in statuses if item[1].get("phase") == "agent_quality_retry"]
    assert len(retry_events) == 1


def test_quality_retry_excludes_gemini_35_flash_from_model_override(monkeypatch):
    calls = []
    model_overrides = []
    bad_decision_output = (
        "## 最終投資決策\n"
        "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。"
    )
    clean_decision_output = "## 最終投資決策\n採用持有，並將資料口徑差異列為風險限制。"

    async def fake_run_single_agent_async(agent_num, data, context, rotator):
        calls.append(agent_num)
        model_overrides.append(copy.deepcopy(context.get("_model_sequence_override")))
        return bad_decision_output if len(calls) == 1 else clean_decision_output

    async def fake_emit_status_async(progress_callback, message, **kwargs):
        return None

    async def noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr(quality_gates, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(quality_gates, "emit_status_async", fake_emit_status_async)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop_async)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop_async)
    monkeypatch.setattr(quality_gates, "_try_parse_structured_output", lambda agent_num, result, context: (True, result))

    context = {
        "pipeline_id": "v1",
        "pipeline_label": "Mode A",
        "agent_positions": {7: 7},
        "agent_total": 10,
        "agent_sequence": (11, 1, 2, 3, 20, 4, 5, 6, 21, 7),
        "structured_outputs": {},
        "analyses": {},
        "data": {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
    }

    completed_agent, markdown = asyncio.run(
        quality_gates.run_agent_with_quality_gates_async(
            7,
            context["data"],
            context,
            FakeRotator(),
        )
    )

    assert completed_agent == 7
    assert len(calls) == 2
    assert model_overrides[0] in (None, {})
    assert model_overrides[1] == {7: ["gemini-2.5-flash"]}
    assert context.get("_model_sequence_override") is None
    assert context["analyses"][7] == markdown == clean_decision_output


def test_quality_gates_appends_warning_after_quality_retry_still_fails(monkeypatch):
    calls = []
    statuses = []
    bad_financial_output = (
        "## 財務分析\n"
        "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。"
    )

    async def fake_run_single_agent_async(agent_num, data, context, rotator):
        calls.append(agent_num)
        return bad_financial_output

    async def fake_emit_status_async(progress_callback, message, **kwargs):
        statuses.append((message, kwargs))

    async def noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setattr(quality_gates, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(quality_gates, "emit_status_async", fake_emit_status_async)
    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", noop_async)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", noop_async)

    context = {
        "pipeline_id": "v1",
        "pipeline_label": "Mode A",
        "agent_positions": {2: 2},
        "agent_total": 10,
        "agent_sequence": (11, 1, 2, 3, 20, 4, 5, 6, 21, 7),
        "structured_outputs": {},
        "analyses": {},
        "data": {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
    }

    completed_agent, markdown = asyncio.run(
        quality_gates.run_agent_with_quality_gates_async(
            2,
            context["data"],
            context,
            FakeRotator(),
        )
    )

    assert completed_agent == 2
    assert len(calls) == 2
    assert context["agent_quality_retry_counts"] == {2: 1}
    assert "系統品質檢查警示" in markdown
    assert "杜邦分析紅線" in markdown
    retry_events = [item for item in statuses if item[1].get("phase") == "agent_quality_retry"]
    assert len(retry_events) == 1


def test_sync_quality_gate_retries_financial_redline_without_gemini_35(monkeypatch):
    calls = []
    model_overrides = []
    statuses = []
    bad_decision_output = (
        "## 最終投資決策\n"
        "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。"
    )
    clean_decision_output = "## 最終投資決策\n採用持有，並將資料口徑差異列為風險限制。"

    def fake_run_single_agent(agent_num, data, context, rotator):
        calls.append(agent_num)
        model_overrides.append(copy.deepcopy(context.get("_model_sequence_override")))
        return clean_decision_output

    def fake_emit_status(progress_callback, message, **kwargs):
        statuses.append((message, kwargs))

    monkeypatch.setattr(pipeline_sync, "run_single_agent", fake_run_single_agent)
    monkeypatch.setattr(pipeline_sync, "emit_status", fake_emit_status)

    context = {"structured_outputs": {}, "analyses": {}}
    result = pipeline_sync._apply_sync_quality_gates(
        7,
        "最終投資決策",
        {"ticker": "2330.TW", "company_name": "台積電", "current_price": 100},
        context,
        FakeRotator(),
        bad_decision_output,
        None,
        7,
        10,
        {"id": "v1", "label": "Mode A"},
    )

    assert result == clean_decision_output
    assert calls == [7]
    assert model_overrides == [{7: ["gemini-2.5-flash"]}]
    assert context.get("_model_sequence_override") is None
    assert context["agent_quality_retry_counts"] == {7: 1}
    retry_events = [item for item in statuses if item[1].get("phase") == "agent_quality_retry"]
    assert len(retry_events) == 1
