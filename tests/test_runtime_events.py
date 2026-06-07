import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from runtime_events import (  # noqa: E402
    RUNTIME_EVENT_LOG_KEY,
    classify_runtime_error,
    emit_context_error,
    emit_context_event,
    emit_context_event_async,
    emit_progress,
    emit_runtime_event,
    emit_runtime_event_async,
    emit_status,
    format_event_log_line,
    make_runtime_error_event,
    make_runtime_event,
)


def test_emit_runtime_event_supports_new_callback_signature():
    events = []

    emit_runtime_event(lambda event: events.append(event), {"type": "status", "message": "hello"})

    assert events == [{"type": "status", "message": "hello"}]


def test_emit_status_supports_legacy_five_arg_callback():
    calls = []

    def callback(current, total, name, phase, message):
        calls.append((current, total, name, phase, message))

    emit_status(
        callback,
        "Agent 2 正在呼叫模型...",
        phase="model_call",
        current=2,
        total=7,
        name="競爭優勢分析",
    )

    assert calls == [(2, 7, "競爭優勢分析", "model_call", "Agent 2 正在呼叫模型...")]


def test_emit_progress_supports_legacy_three_arg_callback():
    calls = []

    def callback(current, total, name):
        calls.append((current, total, name))

    emit_progress(callback, 3, 7, "估值分析")

    assert calls == [(3, 7, "估值分析")]


def test_emit_runtime_event_async_awaits_callback():
    events = []

    async def callback(event):
        events.append(event)

    asyncio.run(emit_runtime_event_async(callback, {"type": "status", "message": "async"}))

    assert events == [{"type": "status", "message": "async"}]


def test_emit_context_event_records_and_forwards():
    context = {}
    forwarded = []

    emit_context_event(
        context,
        {"type": "status", "phase": "model_fallback", "message": "fallback", "_private": "hidden"},
        lambda event: forwarded.append(event),
    )

    assert forwarded[0]["phase"] == "model_fallback"
    assert context[RUNTIME_EVENT_LOG_KEY] == [{"type": "status", "phase": "model_fallback", "message": "fallback"}]


def test_emit_context_event_async_records_and_forwards():
    context = {}
    forwarded = []

    async def callback(event):
        forwarded.append(event)

    asyncio.run(emit_context_event_async(context, {"type": "status", "message": "async-context"}, callback))

    assert forwarded == [{"type": "status", "message": "async-context"}]
    assert context[RUNTIME_EVENT_LOG_KEY] == [{"type": "status", "message": "async-context"}]


def test_format_event_log_line_has_stable_summaries():
    assert (
        format_event_log_line("abcdef123456", {"type": "progress", "current": 2, "total": 7, "name": "Agent A"})
        == "[job abcdef12] progress: Agent 2/7 完成：Agent A"
    )
    assert (
        format_event_log_line("abcdef123456", {"type": "status", "message": "模型呼叫中", "detail": "v1 · Agent A"})
        == "[job abcdef12] status: 模型呼叫中 | v1 · Agent A"
    )
    assert (
        format_event_log_line("abcdef123456", {"type": "done", "filename": "report.html"})
        == "[job abcdef12] done: 報告生成完成：report.html"
    )
    assert (
        format_event_log_line("abcdef123456", {"type": "error", "message": "boom"}, prefix="stream")
        == "[stream abcdef12] error: 錯誤：boom"
    )


def test_runtime_event_schema_preserves_frontend_contract_fields():
    event = make_runtime_event(
        "status",
        phase="model_call",
        level="info",
        message="calling",
        detail="v1 · Agent 7",
        current=7,
        total=7,
        name="投資決策",
        agent_num=7,
        pipeline_id="v1",
        pipeline_label="模式 A",
        metadata={"model_id": "fake-model", "timeout_seconds": 120},
    )

    assert event == {
        "type": "status",
        "phase": "model_call",
        "level": "info",
        "message": "calling",
        "detail": "v1 · Agent 7",
        "current": 7,
        "total": 7,
        "name": "投資決策",
        "agent_num": 7,
        "pipeline_id": "v1",
        "pipeline_label": "模式 A",
        "metadata": {"model_id": "fake-model", "timeout_seconds": 120},
    }


def test_runtime_error_event_classifies_common_failures():
    assert classify_runtime_error(RuntimeError("429 quota exhausted")) == "quota"
    assert classify_runtime_error(TimeoutError("deadline exceeded")) == "timeout"
    assert classify_runtime_error(RuntimeError("response schema validation failed")) == "schema"

    event = make_runtime_error_event(
        "llm_model_error",
        RuntimeError("provider down"),
        message="模型呼叫失敗",
        agent_num=7,
        metadata={"model_id": "fake"},
    )

    assert event["phase"] == "llm_model_error"
    assert event["metadata"]["error_kind"] == "RuntimeError"
    assert event["metadata"]["error_category"] == "provider"
    assert event["metadata"]["model_id"] == "fake"


def test_emit_context_error_records_structured_metadata():
    context = {}

    emit_context_error(context, "final_audit_repair_failed", RuntimeError("repair exploded"), error_category="repair_failed")

    event = context[RUNTIME_EVENT_LOG_KEY][0]
    assert event["phase"] == "final_audit_repair_failed"
    assert event["metadata"]["error_category"] == "repair_failed"
    assert event["metadata"]["error_kind"] == "RuntimeError"


def test_emit_log_uses_runtime_logger(monkeypatch):
    import runtime_events

    calls = []
    monkeypatch.setattr(runtime_events, "log_runtime_message", lambda message, level="info": calls.append((message, level)))

    runtime_events.emit_log("hello", level="warning")

    assert calls == [("hello", "warning")]
