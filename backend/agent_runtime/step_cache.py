"""Deterministic cache for reusable agent step outputs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cache_store import get_cache_json, set_cache_json
from config import AGENT_STEP_CACHE_ENABLED, AGENT_STEP_CACHE_SECONDS
from data_trust_snapshot import sanitize_for_snapshot


PROMPT_VERSION_DEFAULT = "runtime_rules:unversioned"


def build_agent_step_cache_key(
    agent_num: int,
    data: dict,
    context: dict,
    model_id: str,
    prompt: str,
) -> str:
    key_parts = {
        "ticker": str(context.get("ticker") or data.get("ticker") or ""),
        "data_snapshot_hash": _data_snapshot_hash(data, context),
        "agent_id": str(agent_num),
        "prompt_version": _prompt_version(data, context),
        "model_id": str(model_id or ""),
        "prompt_hash": _sha256_text(prompt),
    }
    encoded = json.dumps(key_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "agent_step:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_cached_agent_step(cache_key: str) -> dict | None:
    if not AGENT_STEP_CACHE_ENABLED:
        return None
    try:
        cached = get_cache_json(cache_key)
    except Exception:
        return None
    if not isinstance(cached, dict) or not str(cached.get("text") or "").strip():
        return None
    return cached


def store_cached_agent_step(
    cache_key: str,
    *,
    agent_num: int,
    context: dict,
    model_id: str,
    text: str,
) -> None:
    if not AGENT_STEP_CACHE_ENABLED or AGENT_STEP_CACHE_SECONDS <= 0:
        return
    payload = {
        "schema_version": 1,
        "agent_num": agent_num,
        "model_id": str(model_id or ""),
        "text": str(text or ""),
        "structured_output": _structured_output_for_agent(context, agent_num),
    }
    try:
        set_cache_json(cache_key, payload, AGENT_STEP_CACHE_SECONDS)
    except Exception:
        return


def restore_cached_agent_step(context: dict, agent_num: int, cached: dict) -> str:
    structured = cached.get("structured_output")
    if isinstance(structured, dict):
        context.setdefault("structured_outputs", {})[agent_num] = structured
    stats = context.setdefault("agent_step_cache", {"hits": 0, "misses": 0})
    stats["hits"] = int(stats.get("hits") or 0) + 1
    return str(cached.get("text") or "")


def record_agent_step_cache_miss(context: dict) -> None:
    stats = context.setdefault("agent_step_cache", {"hits": 0, "misses": 0})
    stats["misses"] = int(stats.get("misses") or 0) + 1


def _structured_output_for_agent(context: dict, agent_num: int) -> dict | None:
    outputs = context.get("structured_outputs") if isinstance(context, dict) else {}
    if not isinstance(outputs, dict):
        return None
    value = outputs.get(agent_num, outputs.get(str(agent_num)))
    return sanitize_for_snapshot(value) if isinstance(value, dict) else None


def _data_snapshot_hash(data: dict, context: dict) -> str:
    for source in (context, data):
        for key in ("data_snapshot_hash", "snapshot_hash", "content_hash"):
            value = source.get(key) if isinstance(source, dict) else None
            if str(value or "").strip():
                return str(value).strip()
    encoded = json.dumps(sanitize_for_snapshot(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "data:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _prompt_version(data: dict, context: dict) -> str:
    for source in (context, data):
        value = source.get("prompt_version") if isinstance(source, dict) else None
        if str(value or "").strip():
            return str(value).strip()
    return PROMPT_VERSION_DEFAULT


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
