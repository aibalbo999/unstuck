import asyncio
import sqlite3
import json

import pytest


@pytest.mark.parametrize("asynchronous", [False, True])
def test_resume_with_one_repair_left_cannot_spend_two(asynchronous, monkeypatch):
    from agent_runtime import repair_loop as loop
    calls = []
    context = {"analyses": {16: "original"}, "repair_attempt_counts": {"16": 1}}
    def send(*args, **kwargs):
        calls.append(True)
        return "incomplete candidate"
    async def send_async(*args, **kwargs):
        return send(*args, **kwargs)
    monkeypatch.setattr(loop, "run_single_agent", send)
    monkeypatch.setattr(loop, "run_single_agent_async", send_async)
    monkeypatch.setattr(loop, "repair_429_circuit_state", lambda _: {})
    monkeypatch.setattr(loop, "validate_analysis_output", lambda *a: ["invalid"])
    monkeypatch.setattr(loop, "record_quality_fallback", lambda *a: (False, "unavailable"))
    args = 16, {}, context, object(), ["invalid"]
    asyncio.run(loop._repair_agent_output_async(*args)) if asynchronous else loop._repair_agent_output(*args)
    assert len(calls) == 1
    assert context["repair_attempt_counts"][16] == 2


def test_circuit_skip_is_local_and_not_a_provider_failure():
    from agent_runtime.retry_error_classification import _agent_error_category
    from llm_model_circuits import ModelCircuitOpenError
    assert _agent_error_category(ModelCircuitOpenError("model", 60)) == "local_model_circuit"


def test_historical_local_errors_excluded_from_provider_dashboard():
    from job_ops_dashboard_provider_errors import provider_error_rows
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE api_usage_events (id INTEGER, service TEXT, operation TEXT, model_id TEXT, status TEXT, metadata_json TEXT)")
    for n, kind in enumerate(["ModelCircuitOpenError", "AllKeysRpdDisabledError", "KeyAdmissionTimeout", "ClientError"]):
        conn.execute("INSERT INTO api_usage_events VALUES (?, 'Gemini / Google AI', 'llm_model_error', 'model', 'quota_error', ?)",
                     (n, json.dumps({"error_kind": kind, "provider_status_code": 429 if kind == "ClientError" else None})))
    rows = provider_error_rows(conn, 100)
    assert len(rows) == 1
    assert rows[0]["provider_status_code"] == 429


def test_report_metrics_do_not_count_errors_as_requests_or_unknown_as_zero():
    from report_execution_metrics import report_execution_metrics
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""CREATE TABLE analysis_jobs (job_id TEXT, ticker TEXT, pipeline_id TEXT, status TEXT, filename TEXT, created_at REAL, updated_at REAL, finished_at REAL);
      CREATE TABLE api_usage_events (id INTEGER, service TEXT, operation TEXT, metadata_json TEXT);
      CREATE TABLE analysis_events (id INTEGER, job_id TEXT, payload TEXT);
      INSERT INTO analysis_jobs VALUES ('ok','T','v2','done','report.html',100,200,200), ('old','O','v4','done','old.html',100,200,200), ('retry','R','v3','waiting_retry',NULL,100,200,NULL), ('partial','P','rerun:valuation','done','partial.html',1,9999,9999);""")
    for n, (job, operation, kind) in enumerate([('ok','llm_provider_request',''), ('ok','llm_provider_request',''), ('ok','llm_model_error','ClientError'), ('retry','llm_model_error','ModelCircuitOpenError')]):
        c.execute("INSERT INTO api_usage_events VALUES (?, 'Gemini / Google AI', ?, ?)", (n, operation, json.dumps({'job_id':job,'error_kind':kind,'agent_num':16})))
    c.execute("INSERT INTO analysis_events VALUES (1,'retry',?)", (json.dumps({'phase':'model_circuit_open','agent_num':19,'metadata':{'model_id':'m','reason_code':'provider_daily_quota_exhausted'}}),))
    result = report_execution_metrics(c)
    assert result['sample_size'] == 3
    assert result['mean_observed_requests_per_completed_report'] == 2
    assert result['completed_with_request_evidence'] == 1
    assert result['mean_completed_elapsed_seconds'] == 100
    by_id = {r['job_id']:r for r in result['reports']}
    assert by_id['old']['observed_provider_requests'] is None
    assert by_id['retry']['local_blocks'] == 1
    assert by_id['retry']['provider_errors'] == 0
    assert result['route_skips'] == [{'model_id':'m','reason_code':'provider_daily_quota_exhausted','count':1}]
