"""Telemetry event adapter for analysis jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from job_store import append_event, record_node_telemetry, sanitize_error_message


TelemetryRecorder = Callable[[dict[str, Any]], None]
EventAppender = Callable[[str, dict[str, Any]], None]
ErrorSanitizer = Callable[[Any], Any]


def analysis_node_telemetry_payload(
    payload: dict[str, Any] | None,
    *,
    job_id: str,
    ticker_upper: str,
    run_id: str,
) -> dict[str, Any]:
    raw = dict(payload or {})
    return {
        **raw,
        "job_id": job_id,
        "ticker": ticker_upper,
        "pipeline_id": str(raw.get("pipeline_id") or run_id),
    }


def analysis_node_telemetry_event(
    telemetry_payload: dict[str, Any],
    *,
    sanitize_error_func: ErrorSanitizer = sanitize_error_message,
) -> dict[str, Any]:
    return {
        "type": "telemetry",
        "node_name": telemetry_payload.get("node_name"),
        "model": telemetry_payload.get("model"),
        "status": telemetry_payload.get("status"),
        "latency_ms": telemetry_payload.get("latency_ms"),
        "retry_count": telemetry_payload.get("retry_count", 0),
        "quality_gate_pass": telemetry_payload.get("quality_gate_pass"),
        "error": sanitize_error_func(telemetry_payload.get("error")),
        "pipeline_id": telemetry_payload.get("pipeline_id"),
    }


def make_analysis_job_telemetry_callback(
    *,
    job_id: str,
    ticker_upper: str,
    run_id: str,
    record_telemetry_func: TelemetryRecorder = record_node_telemetry,
    append_event_func: EventAppender = append_event,
    sanitize_error_func: ErrorSanitizer = sanitize_error_message,
) -> Callable[[dict[str, Any] | None], None]:
    def telemetry_callback(payload: dict[str, Any] | None) -> None:
        telemetry_payload = analysis_node_telemetry_payload(
            payload,
            job_id=job_id,
            ticker_upper=ticker_upper,
            run_id=run_id,
        )
        record_telemetry_func(telemetry_payload)
        append_event_func(
            job_id,
            analysis_node_telemetry_event(
                telemetry_payload,
                sanitize_error_func=sanitize_error_func,
            ),
        )

    return telemetry_callback
