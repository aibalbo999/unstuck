"""Bounded provider-error parsing with an explicit, secret-safe output schema."""

from __future__ import annotations

import json
import math
import re


def extract_quota_details(error) -> dict:
    result = {"violations": [], "retry_delay_seconds": None}
    pending = [(getattr(error, name, None), 0) for name in ("details", "message", "response_json")]
    pending.append((str(error)[:100_000], 0))
    visited = 0
    while pending and visited < 300:
        value, depth = pending.pop()
        visited += 1
        if depth > 8:
            continue
        if isinstance(value, str) and len(value) <= 100_000:
            start = value.find("{")
            if start >= 0:
                try:
                    parsed, _ = json.JSONDecoder().raw_decode(value[start:])
                    pending.append((parsed, depth + 1))
                except (ValueError, RecursionError):
                    pass
        elif isinstance(value, list):
            pending.extend((item, depth + 1) for item in value[:100])
        elif isinstance(value, dict):
            violation = _violation(value)
            if violation and violation not in result["violations"] and len(result["violations"]) < 12:
                result["violations"].append(violation)
            delay = value.get("retryDelay")
            if isinstance(delay, str) and re.fullmatch(r"\d{1,6}(?:\.\d{1,6})?s", delay):
                result["retry_delay_seconds"] = max(result["retry_delay_seconds"] or 0, float(delay[:-1]))
            pending.extend((item, depth + 1) for item in list(value.values())[:100] if isinstance(item, (dict, list, str)))
    return result


def _violation(value):
    identifier = " ".join(str(value.get(key) or "")[:300] for key in ("quotaId", "quotaMetric"))
    compact = re.sub(r"[^a-z0-9]", "", identifier.lower())
    if "requestsperday" in compact:
        kind = "rpd"
    elif "requestsperminute" in compact:
        kind = "rpm"
    elif "tokensperminute" in compact or "tokenspermodelperminute" in compact:
        kind = "input_tpm" if "input" in compact else "tpm"
    else:
        return None
    raw = value.get("quotaValue")
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        return None
    try:
        number = float(raw)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0 or number != int(number):
        return None
    result = {"kind": kind, "limit": int(number)}
    dimensions = value.get("quotaDimensions")
    model = dimensions.get("model") if isinstance(dimensions, dict) else None
    if isinstance(model, str) and re.fullmatch(r"(?:gemini|gemma)-[a-z0-9.\-]{1,90}", model):
        result["model"] = model
    return result


def describe_quota_details(error):
    details = extract_quota_details(error)
    labels = {"input_tpm": "每分鐘輸入 token 額度（TPM）", "tpm": "每分鐘 token 額度（TPM）",
              "rpm": "每分鐘請求額度（RPM）", "rpd": "每日請求額度（RPD）"}
    parts = [f"{labels[item['kind']]}={item['limit']}" for item in details["violations"]]
    if not parts:
        parts = ["Google API 配額或速率限制（未提供可驗證細項）"]
    if details["retry_delay_seconds"] is not None:
        parts.append(f"retryDelay={details['retry_delay_seconds']:g}s")
    return "；".join(parts)
