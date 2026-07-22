import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent_runtime.single_agent_events import (  # noqa: E402
    emit_async_model_event,
    emit_sync_model_event,
    single_agent_event_fields,
)


def test_single_agent_event_fields_preserve_pipeline_and_metadata():
    context = {
        "agent_positions": {7: 2},
        "agent_total": 4,
        "pipeline_id": "v4",
        "pipeline_label": "Full",
    }

    fields = single_agent_event_fields(context, 7, "gemini", cache_key="abc", cache_hit=True, skipped=None)

    assert fields == {
        "current": 2,
        "total": 4,
        "name": "Agent 7",
        "agent_num": 7,
        "pipeline_id": "v4",
        "pipeline_label": "Full",
        "metadata": {"model_id": "gemini", "cache_key": "abc", "cache_hit": True},
    }


def test_single_agent_model_event_emitters_store_runtime_events():
    sync_context = {"agent_total": 1}
    emit_sync_model_event(sync_context, 3, "model_fallback", "warning", "fallback", "gemini", model_index=1)

    assert sync_context["_runtime_events"][0]["phase"] == "model_fallback"
    assert sync_context["_runtime_events"][0]["metadata"] == {"model_id": "gemini", "model_index": 1}

    async_context = {"agent_total": 1}
    asyncio.run(
        emit_async_model_event(async_context, 3, "model_circuit_open", "warning", "circuit", "gemini")
    )

    assert async_context["_runtime_events"][0]["phase"] == "model_circuit_open"
    assert async_context["_runtime_events"][0]["metadata"] == {"model_id": "gemini"}
