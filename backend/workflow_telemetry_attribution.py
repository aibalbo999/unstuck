"""Invocation- and output-bound receipts for workflow model attribution.

These receipts describe one returned agent result, not all provider calls made
while producing it. Provider attempt/cost accounting remains in call events.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

from security_sanitizer import sanitize_error_message


RECEIPT_KEY = "node_telemetry"
SCHEMA_VERSION = 1
_invocation: ContextVar[dict | None] = ContextVar("node_telemetry_invocation", default=None)


@contextmanager
def node_telemetry_scope(node_name: str, agent_num: int | None):
    token = _invocation.set({"invocation_id": uuid4().hex, "node_name": node_name, "agent_num": agent_num})
    try:
        yield
    finally:
        _invocation.reset(token)


def current_node_invocation() -> dict | None:
    value = _invocation.get()
    return dict(value) if value is not None else None


def result_fingerprint(result: dict, agent_num: int) -> str | None:
    """Bind only the current agent's returned analysis and structured output."""
    analyses = result.get("analyses")
    if not isinstance(analyses, dict):
        return None
    text = analyses.get(str(agent_num), analyses.get(agent_num))
    if not isinstance(text, str) or not text.strip():
        return None
    outputs = result.get("structured_outputs")
    structured = outputs.get(str(agent_num), outputs.get(agent_num)) if isinstance(outputs, dict) else None
    try:
        encoded = json.dumps({"analysis": text, "structured": structured}, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def safe_model_label(value) -> str | None:
    if not isinstance(value, str) or not 0 < len(value) <= 160:
        return None
    if sanitize_error_message(value) != value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", value):
        return None
    return value


def optional_count(value) -> int | None:
    # Do not coerce strings, floats, booleans, or invalid usage into real counts.
    return value if type(value) is int and 0 <= value < (1 << 63) else None


def result_telemetry(result, node_name: str, agent_num: int | None) -> dict:
    unknown = {"model": None, "input_tokens": None, "output_tokens": None,
               "cache_hit": False, "retry_count": 0, "quality_gate_pass": None}
    invocation = current_node_invocation()
    if (not isinstance(result, dict) or agent_num is None or node_name != f"agent_{agent_num}"
            or invocation is None):
        return unknown
    receipt = result.get(RECEIPT_KEY)
    if not isinstance(receipt, dict) or receipt.get("schema_version") != SCHEMA_VERSION:
        return unknown
    if any(receipt.get(key) != invocation[key] for key in ("invocation_id", "node_name", "agent_num")):
        return unknown
    fingerprint = result_fingerprint(result, agent_num)
    if fingerprint is None or receipt.get("result_fingerprint") != fingerprint:
        return unknown
    model = safe_model_label(receipt.get("model"))
    quality = receipt.get("quality_gate_pass")
    return {
        "model": model,
        "input_tokens": optional_count(receipt.get("input_tokens")) if model else None,
        "output_tokens": optional_count(receipt.get("output_tokens")) if model else None,
        "cache_hit": receipt.get("cache_hit") is True,
        "retry_count": (optional_count(receipt.get("retry_count")) or 0) if model else 0,
        "quality_gate_pass": quality if type(quality) is bool else None,
    }
