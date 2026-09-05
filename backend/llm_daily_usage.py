"""Read-only demand profiles; ledger observations are not provider quota."""

from __future__ import annotations

import json
import math
from collections import deque
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


LOCAL_BLOCK_KINDS = {"ModelCircuitOpenError", "AllKeysRpdDisabledError", "InputCapacityExceededError", "DailyBudgetBlockedError", "ToolRequestGuardError"}
COUNTS = ("requests", "success_events", "provider_quota_errors", "local_blocks", "other_errors", "unclassified_quota_errors")


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if math.isfinite(value) and value >= 0 and value == int(value) else None


def _bucket():
    return {**dict.fromkeys(COUNTS, 0), "_inputs": [], "_terminal_events": 0, "model_requests": {}}


def _finish(bucket):
    values = sorted(bucket.pop("_inputs"))
    terminal = bucket.pop("_terminal_events")
    bucket["input_tokens"] = {
        "total": sum(values) if values else None,
        "samples": len(values),
        "terminal_events": terminal,
        "coverage_pct": round(100 * len(values) / terminal, 1) if terminal else None,
        "p50": values[math.ceil(len(values) * .5) - 1] if values else None,
        "p95": values[math.ceil(len(values) * .95) - 1] if values else None,
        "max": max(values) if values else None,
    }
    return bucket


def build_daily_usage_profile(rows, *, now: datetime, days=14, timezone="Asia/Taipei", ledger_started_at=None):
    """Include complete calendar days plus today, excluding partial days from averages."""
    tz = ZoneInfo(timezone)
    now = now.astimezone(tz)
    days = max(1, min(int(days), 90))
    start_date = now.date() - timedelta(days=days)
    start = datetime.combine(start_date, time(), tzinfo=tz).timestamp()
    daily = {}
    for offset in range(days + 1):
        date = start_date + timedelta(days=offset)
        midnight = datetime.combine(date, time(), tzinfo=tz).timestamp()
        daily[date.isoformat()] = {
            "date": date.isoformat(), "is_complete": date < now.date() and ledger_started_at is not None and ledger_started_at <= midnight,
            **_bucket(),
        }
    models = {}
    requests = []
    for row in rows:
        ts = row["created_at"]
        if not start <= ts <= now.timestamp():
            continue
        operation = row["operation"]
        if operation not in {"llm_provider_request", "llm_model_response", "llm_model_error"}:
            continue
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (ValueError, TypeError):
            metadata = {}
        metadata = metadata if isinstance(metadata, dict) else {}
        model = str(row["model_id"] or "unknown")
        targets = [daily[datetime.fromtimestamp(ts, tz).date().isoformat()], models.setdefault(model, _bucket())]
        local = metadata.get("error_kind") in LOCAL_BLOCK_KINDS
        if operation == "llm_provider_request":
            units = _count(row["units"]) or 0
            requests.append((ts, units, model))
            for target in targets:
                target["requests"] += units
                target["model_requests"][model] = target["model_requests"].get(model, 0) + units
            continue
        if operation == "llm_model_response":
            field = "success_events"
        elif local:
            field = "local_blocks"
        elif row["status"] in {"quota_error", "rate_limited"}:
            field = "provider_quota_errors" if metadata.get("error_kind") == "ClientError" else "unclassified_quota_errors"
        else:
            field = "other_errors"
        diagnostics = metadata.get("response_diagnostics")
        usage = diagnostics.get("usage") if isinstance(diagnostics, dict) else None
        input_tokens = _count(usage.get("input_tokens")) if isinstance(usage, dict) else None
        for target in targets:
            target[field] += 1
            if not local:
                target["_terminal_events"] += 1
                if input_tokens is not None:
                    target["_inputs"].append(input_tokens)
    window = deque()
    total = peak = 0
    model_window = {}
    model_peaks = {}
    for ts, units, model in sorted(requests):
        while window and window[0][0] <= ts - 60:
            _, old_units, old_model = window.popleft()
            total -= old_units
            model_window[old_model] -= old_units
        window.append((ts, units, model))
        total += units
        model_window[model] = model_window.get(model, 0) + units
        peak = max(peak, total)
        model_peaks[model] = max(model_peaks.get(model, 0), model_window[model])
    entries = [_finish(bucket) for bucket in daily.values()]
    complete = [entry for entry in entries if entry["is_complete"]]
    for model, bucket in models.items():
        _finish(bucket)
        bucket["peak_requests_60s"] = model_peaks.get(model, 0)
        counts = [entry["model_requests"].get(model, 0) for entry in complete]
        bucket["average_daily_requests"] = round(sum(counts) / len(counts), 1) if counts else None
        bucket["peak_daily_requests"] = max(counts) if counts else None
    return {
        "ledger_source": "api_usage_events", "basis": "observed_agent_request_events_not_billing",
        "coverage_note": "歷史 ledger 主要涵蓋 Agent 請求事件；摘要、embedding 與快取命中可能未完整區分，並非 Google 全部實際用量。",
        "timezone": timezone, "generated_at": now.isoformat(timespec="seconds"), "lookback_days": days,
        "daily": entries, "today": entries[-1], "models": models, "peak_requests_60s": peak,
        "complete_days": {"count": len(complete), "requests": sum(entry["requests"] for entry in complete),
                          "average_requests": round(sum(entry["requests"] for entry in complete) / len(complete), 1) if complete else None,
                          "peak_requests": max(entry["requests"] for entry in complete) if complete else None},
    }
