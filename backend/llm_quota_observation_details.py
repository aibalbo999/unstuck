"""Versioned quota observations. Never used by admission or retry decisions."""
from __future__ import annotations

from functools import lru_cache
from importlib.metadata import version
import json
import math
import re

from llm_quota_details import _header_retry_delay

PARSER_VERSION = "quota-observation-v1"


@lru_cache(maxsize=1)
def sdk_version():
    try:
        return version("google-genai")
    except Exception:
        return None


def _identifier(value, pattern):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
        return int(number) if math.isfinite(number) and 0 <= number <= 2**63-1 and number.is_integer() else None
    except (ValueError, OverflowError):
        return None


def _violation(value):
    identifier = _identifier(value.get("quotaId"), r"(?:Generate|Embed|Batch|Ground|Search)[A-Za-z0-9_-]{0,180}")
    metric = _identifier(value.get("quotaMetric"), r"[a-z][a-z0-9.-]{0,80}\.googleapis\.com/[a-zA-Z_][a-zA-Z0-9_./-]{0,180}")
    if identifier is None and metric is None:
        return None
    compact = re.sub(r"[^a-z0-9]", "", ((identifier or "") + (metric or "")).lower())
    kind = ("rpd" if "requestsperday" in compact else "rpm" if "requestsperminute" in compact else
            "input_tpm" if "inputtokensper" in compact else
            "tpm" if "tokensperminute" in compact or "tokenspermodelperminute" in compact else "unknown")
    result = {"kind": kind, "limit": _number(value.get("quotaValue")),
              "quota_id": identifier, "quota_metric": metric}
    dimensions = value.get("quotaDimensions")
    if isinstance(dimensions, dict):
        model = _identifier(dimensions.get("model"), r"(?:gemma|gemini)-[a-z0-9.\-]{1,90}")
        if model:
            result["model"] = model
        if dimensions.get("location") == "global":
            result["location"] = "global"
    return result


def _observe_quota_details(error):
    result = {"schema_version": 1, "parser_version": PARSER_VERSION, "sdk_version": sdk_version(),
              "detail_status": "sdk_fields_absent", "violations": [], "retry_delay_seconds": None,
              "source_fields": [], "truncated": False}
    pending = []
    for name in ("details", "message", "response_json"):
        try:
            value = getattr(error, name, None)
        except Exception:
            continue
        if value is not None:
            result["source_fields"].append(name)
            pending.append((value, 0))
    try:
        result["retry_delay_seconds"] = _header_retry_delay(error)
    except Exception:
        pass
    malformed = False
    visited = 0
    while pending and visited < 300:
        value, depth = pending.pop()
        visited += 1
        if depth > 8:
            result["truncated"] = True
            continue
        if isinstance(value, str):
            if len(value) > 100_000:
                result["truncated"] = True
                continue
            offset = value.find("{")
            if offset >= 0:
                try:
                    parsed, _ = json.JSONDecoder().raw_decode(value[offset:])
                    pending.append((parsed, depth+1))
                except (ValueError, RecursionError):
                    malformed = True
        elif isinstance(value, list):
            result["truncated"] |= len(value) > 100
            pending.extend((child, depth+1) for child in value[:100])
        elif isinstance(value, dict):
            violation = _violation(value)
            if violation and violation not in result["violations"]:
                if len(result["violations"]) < 12:
                    result["violations"].append(violation)
                else:
                    result["truncated"] = True
            delay = value.get("retryDelay")
            if isinstance(delay, str) and re.fullmatch(r"\d{1,6}(?:\.\d{1,9})?s", delay):
                result["retry_delay_seconds"] = max(result["retry_delay_seconds"] or 0, float(delay[:-1]))
            result["truncated"] |= len(value) > 100
            pending.extend((child, depth+1) for child in list(value.values())[:100]
                           if isinstance(child, (dict, list, str)))
    result["truncated"] |= bool(pending)
    violations = result["violations"]
    if violations:
        result["detail_status"] = ("unrecognized" if all(v["kind"] == "unknown" for v in violations) else
                                   "partial" if malformed or result["truncated"] or any(v["limit"] is None or v["kind"] == "unknown" for v in violations) else "parsed")
    elif malformed:
        result["detail_status"] = "parse_error"
    elif result["source_fields"]:
        result["detail_status"] = "no_supported_details"
    return result


def observe_quota_details(error):
    try:
        return _observe_quota_details(error)
    except Exception:
        return {'schema_version': 1, 'parser_version': PARSER_VERSION, 'sdk_version': None,
                'detail_status': 'observation_unavailable', 'violations': [],
                'retry_delay_seconds': None, 'source_fields': [], 'truncated': False}
