import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent_runtime import quality_structured_outputs  # noqa: E402


def test_try_parse_structured_output_skips_non_structured_agents(monkeypatch):
    calls = []

    def fake_process_agent_response(agent_num, result, context):
        calls.append((agent_num, result, context))
        return "parsed"

    monkeypatch.setattr(quality_structured_outputs, "process_agent_response", fake_process_agent_response)

    ok, result = quality_structured_outputs.try_parse_structured_output(
        2,
        "raw markdown",
        {"pipeline_id": "v1", "structured_outputs": {}},
    )

    assert ok is True
    assert result == "raw markdown"
    assert calls == []


def test_try_parse_structured_output_keeps_existing_structured_payload(monkeypatch):
    calls = []

    def fake_process_agent_response(agent_num, result, context):
        calls.append((agent_num, result, context))
        return "parsed"

    monkeypatch.setattr(quality_structured_outputs, "process_agent_response", fake_process_agent_response)

    ok, result = quality_structured_outputs.try_parse_structured_output(
        4,
        "raw markdown",
        {"pipeline_id": "v1", "structured_outputs": {4: {"price_targets": {}}}},
    )

    assert ok is True
    assert result == "raw markdown"
    assert calls == []


def test_try_parse_structured_output_returns_parsed_result_when_parser_persists_payload(monkeypatch):
    def fake_process_agent_response(agent_num, result, context):
        context.setdefault("structured_outputs", {})[agent_num] = {"price_targets": {"基本情境": 100}}
        return "parsed markdown"

    monkeypatch.setattr(quality_structured_outputs, "process_agent_response", fake_process_agent_response)
    context = {"pipeline_id": "v1", "structured_outputs": {}}

    ok, result = quality_structured_outputs.try_parse_structured_output(4, "raw markdown", context)

    assert ok is True
    assert result == "parsed markdown"
    assert context["structured_outputs"][4]["price_targets"]["基本情境"] == 100
