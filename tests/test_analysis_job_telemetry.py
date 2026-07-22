import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from analysis_job_telemetry import make_analysis_job_telemetry_callback  # noqa: E402


def test_analysis_job_telemetry_callback_records_and_appends_sanitized_event():
    recorded = []
    events = []

    callback = make_analysis_job_telemetry_callback(
        job_id="job-1",
        ticker_upper="2330.TW",
        run_id="v4",
        record_telemetry_func=recorded.append,
        append_event_func=lambda job_id, payload: events.append((job_id, payload)),
        sanitize_error_func=lambda error: f"safe:{error}",
    )

    callback(
        {
            "node_name": "agent_7",
            "model": "gemini",
            "status": "error",
            "latency_ms": 123,
            "retry_count": 2,
            "quality_gate_pass": False,
            "error": "raw secret error",
        }
    )

    assert recorded == [
        {
            "node_name": "agent_7",
            "model": "gemini",
            "status": "error",
            "latency_ms": 123,
            "retry_count": 2,
            "quality_gate_pass": False,
            "error": "raw secret error",
            "job_id": "job-1",
            "ticker": "2330.TW",
            "pipeline_id": "v4",
        }
    ]
    assert events == [
        (
            "job-1",
            {
                "type": "telemetry",
                "node_name": "agent_7",
                "model": "gemini",
                "status": "error",
                "latency_ms": 123,
                "retry_count": 2,
                "quality_gate_pass": False,
                "error": "safe:raw secret error",
                "pipeline_id": "v4",
            },
        )
    ]


def test_analysis_job_telemetry_callback_preserves_payload_pipeline_id():
    recorded = []
    events = []
    callback = make_analysis_job_telemetry_callback(
        job_id="job-2",
        ticker_upper="AAPL",
        run_id="both",
        record_telemetry_func=recorded.append,
        append_event_func=lambda job_id, payload: events.append((job_id, payload)),
        sanitize_error_func=lambda error: error,
    )

    callback({"node_name": "agent_1", "pipeline_id": "v1"})

    assert recorded[0]["pipeline_id"] == "v1"
    assert events[0][1]["pipeline_id"] == "v1"
