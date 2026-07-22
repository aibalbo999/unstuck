"""Runtime helpers for context digest generation."""

from __future__ import annotations

import hashlib
import json

from google.genai import types

from agent_catalog import AGENT_NAMES
from cache_store import get_cache_json, set_cache_json
from config import AGENT_STEP_CACHE_ENABLED, AGENT_STEP_CACHE_SECONDS, CONTEXT_DIGEST_MODEL
from prompt_rules import get_task_system_instruction


def _context_digest_model_sequence() -> list[str]:
    return [CONTEXT_DIGEST_MODEL]


def _build_digest_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        response_mime_type="application/json",
        system_instruction=get_task_system_instruction("context_digest"),
    )


def _digest_input_hash(agent_num: int, context: dict) -> str:
    """計算 context digest 的輸入 hash，相同輸入只算一次。"""

    analyses = context.get("analyses", {}) or {}
    relevant_items = []
    for key, value in analyses.items():
        try:
            key_int = int(key)
        except (TypeError, ValueError):
            continue
        if key_int < int(agent_num):
            relevant_items.append((str(key), value))
    payload = json.dumps(
        {key: str(value)[:500] for key, value in sorted(relevant_items)},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _context_digest_cache_key(agent_num: int, input_hash: str, model_id: str, context: dict) -> str:
    key_parts = {
        "agent_num": int(agent_num),
        "input_hash": str(input_hash or ""),
        "model_id": str(model_id or ""),
        "pipeline_id": str(context.get("pipeline_id") or ""),
        "prompt_version": str(context.get("prompt_version") or "runtime_rules:unversioned"),
    }
    encoded = json.dumps(key_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "context_digest:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _get_cached_context_digest(cache_key: str) -> str | None:
    if not AGENT_STEP_CACHE_ENABLED:
        return None
    try:
        cached = get_cache_json(cache_key)
    except Exception:
        return None
    if not isinstance(cached, dict):
        return None
    text = str(cached.get("digest") or "").strip()
    return text or None


def _store_cached_context_digest(cache_key: str, digest: str) -> None:
    if not AGENT_STEP_CACHE_ENABLED or AGENT_STEP_CACHE_SECONDS <= 0 or not str(digest or "").strip():
        return
    try:
        set_cache_json(cache_key, {"schema_version": 1, "digest": digest}, AGENT_STEP_CACHE_SECONDS)
    except Exception:
        return


def _agent_event_kwargs(context: dict, agent_num: int, model_id: str, phase: str, message: str, level: str = "info") -> dict:
    return dict(
        phase=phase,
        level=level,
        message=message,
        current=context.get("agent_positions", {}).get(agent_num, agent_num),
        total=context.get("agent_total"),
        name=AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
        agent_num=agent_num,
        pipeline_id=context.get("pipeline_id"),
        pipeline_label=context.get("pipeline_label"),
        metadata={"model_id": model_id, "task": "context_digest"},
    )
