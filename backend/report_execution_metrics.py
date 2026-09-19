"""Bounded report-level observations; provider calls are not report outcomes."""
import json
import sqlite3
from collections import Counter

from llm_daily_usage import LOCAL_BLOCK_KINDS


def _metadata(value):
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def report_execution_metrics(conn, *, job_limit=100, event_limit=20000):
    result = {"sample_size": 0, "reports": [], "completed_with_request_evidence": 0,
              "mean_observed_requests_per_completed_report": None,
              "mean_completed_elapsed_seconds": None, "route_skips": [],
              "observation_basis": "bounded_ledger_sample; elapsed_includes_queue_and_retry_wait",
              "request_scope": "agent_generation_and_evidence_batches; excludes_digest_and_reflection"}
    try:
        jobs = conn.execute("""SELECT job_id, ticker, pipeline_id, status, filename,
            created_at, updated_at, finished_at FROM analysis_jobs
            WHERE pipeline_id IN ('v1', 'v2', 'v3', 'v4', 'rerun:full_report')
            ORDER BY updated_at DESC LIMIT ?""", (job_limit,)).fetchall()
        rows = conn.execute("""SELECT operation, metadata_json FROM api_usage_events
            WHERE service = 'Gemini / Google AI' ORDER BY id DESC LIMIT ?""", (event_limit,)).fetchall()
        events = conn.execute("SELECT job_id, payload FROM analysis_events ORDER BY id DESC LIMIT ?", (event_limit,)).fetchall()
    except sqlite3.Error:
        result["observability_unavailable"] = True
        return result
    counts, last_agents, event_agents, skips = {}, {}, {}, Counter()
    for row in rows:
        meta = _metadata(row["metadata_json"])
        job_id = str(meta.get("job_id") or "")
        bucket = counts.setdefault(job_id, Counter())
        if row["operation"] == "llm_provider_request":
            bucket["observed_provider_requests"] += 1
        elif row["operation"] == "llm_model_error":
            local = meta.get("error_kind") in LOCAL_BLOCK_KINDS or str(meta.get("error_category") or "").startswith("local_")
            bucket["local_blocks" if local else "provider_errors"] += 1
        if meta.get("agent_num") is not None:
            last_agents.setdefault(job_id, meta["agent_num"])
    for row in events:
        payload = _metadata(row["payload"])
        meta = payload.get("metadata") or {}
        if not isinstance(meta, dict):
            continue
        if payload.get("agent_num") is not None:
            event_agents.setdefault(row["job_id"], payload["agent_num"])
        if payload.get("phase") == "workflow_retry":
            for route in payload.get("routes", meta.get("routes", [])) or []:
                if isinstance(route, dict):
                    skips[(str(route.get("model_id") or "unknown"), str(route.get("reason_code") or "legacy_unspecified"))] += 1
        if payload.get("phase") in {"model_circuit_open", "model_input_capacity", "report_route_unavailable"}:
            reason = meta.get("reason_code") or ("input_capacity" if payload.get("phase") == "model_input_capacity" else "legacy_unspecified")
            skips[(str(meta.get("model_id") or "unknown"), str(reason))] += 1
    for row in jobs:
        item = dict(row)
        bucket = counts.get(item["job_id"])
        item.update({key: bucket[key] if bucket else None for key in ("observed_provider_requests", "provider_errors", "local_blocks")})
        item["last_agent"] = event_agents.get(item["job_id"], last_agents.get(item["job_id"]))
        item["elapsed_seconds"] = max(0, (item["finished_at"] or item["updated_at"]) - item["created_at"])
        result["reports"].append(item)
    completed = [r for r in result["reports"] if r["status"] == "done" and r["filename"]]
    observed = [r for r in completed if r["observed_provider_requests"] is not None and r["observed_provider_requests"] > 0]
    result.update(sample_size=len(jobs), completed_with_request_evidence=len(observed),
                  mean_observed_requests_per_completed_report=round(sum(r["observed_provider_requests"] for r in observed) / len(observed), 2) if observed else None,
                  mean_completed_elapsed_seconds=round(sum(r["elapsed_seconds"] for r in completed) / len(completed), 1) if completed else None,
                  route_skips=[{"model_id": model, "reason_code": reason, "count": count} for (model, reason), count in skips.most_common()])
    return result
