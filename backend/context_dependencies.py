"""Dependency and provenance boundaries shared by prompts and digest caches."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mapping_fields import safe_mapping_dict, safe_text
from pipeline_modes import PIPELINE_DEFINITIONS, get_pipeline_definition
from prompt_evidence import prompt_evidence_copy


DIGEST_SCHEMA_VERSION = "context_digest.v2"


def _mapping(value: Any) -> dict:
    mapped = safe_mapping_dict(value)
    return mapped if mapped is not None else {}


def _pipeline_for_agent(current_agent: int, context: dict):
    context = _mapping(context)
    pipeline_id = safe_text(context.get("pipeline_id")).strip()
    if pipeline_id:
        return get_pipeline_definition(pipeline_id)
    # Legacy callers omit pipeline identity. Infer by membership, never by IDs' order.
    return next((definition for definition in PIPELINE_DEFINITIONS.values() if current_agent in definition["agents"]), get_pipeline_definition())


def upstream_agent_numbers(current_agent: int, context: dict | None = None) -> tuple[int, ...]:
    """Return prior groups only; a peer in the current parallel group is not upstream."""
    upstream = []
    for group in _pipeline_for_agent(current_agent, context)["groups"]:
        if current_agent in group:
            return tuple(upstream)
        upstream.extend(group)
    return ()


def upstream_context_inputs(current_agent: int, context: dict) -> dict:
    """Copy just upstream evidence, dropping internal fields before traversal."""
    context = _mapping(context)
    upstream = upstream_agent_numbers(current_agent, context)
    result = {}
    for section in ("analyses", "structured_outputs"):
        values = _mapping(context.get(section))
        selected = {}
        for agent in upstream:
            value = values.get(agent, values.get(str(agent)))
            if value is not None:
                selected[agent] = prompt_evidence_copy(value)
        result[section] = selected
    return result


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {safe_text(key): _json_value(item) for key, item in dict.items(value)}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def digest_input_hash(current_agent: int, context: dict) -> str:
    """Version all complete source inputs, including structured and prompt revisions."""
    context = _mapping(context)
    payload = {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "pipeline_id": _pipeline_for_agent(current_agent, context)["id"],
        "target_agent": current_agent,
        "upstream_agents": upstream_agent_numbers(current_agent, context),
        "prompt_version": safe_text(context.get("prompt_version")),
        "prompt_fingerprint": safe_text(context.get("prompt_fingerprint")),
        **upstream_context_inputs(current_agent, context),
    }
    encoded = json.dumps(_json_value(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=safe_text)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def digest_provenance(current_agent: int, context: dict) -> dict[str, str]:
    return {"schema_version": DIGEST_SCHEMA_VERSION, "input_hash": digest_input_hash(current_agent, context)}


def digest_matches_input(digest: Any, input_hash: str) -> bool:
    """Legacy strings remain readable checkpoint data, but never count as fresh."""
    if not isinstance(digest, str):
        return False
    try:
        payload = json.loads(digest)
    except (TypeError, ValueError):
        return False
    provenance = _mapping(_mapping(payload).get("digest_provenance"))
    return provenance.get("schema_version") == DIGEST_SCHEMA_VERSION and provenance.get("input_hash") == input_hash


def fresh_context_digest(current_agent: int, context: dict) -> str | None:
    context = _mapping(context)
    digests = _mapping(context.get("context_digests"))
    digest = digests.get(current_agent, digests.get(str(current_agent)))
    return digest if digest_matches_input(digest, digest_input_hash(current_agent, context)) else None


def reuse_digest_cache(current_agent: int, input_hash: str, digests: dict, cache: dict) -> bool:
    """Share version validation between synchronous and asynchronous orchestration."""
    cached = cache.get((current_agent, input_hash))
    existing = digests.get(current_agent, digests.get(str(current_agent)))
    for candidate in (cached, existing):
        if digest_matches_input(candidate, input_hash):
            digests[current_agent] = candidate
            return True
    digests.pop(current_agent, None)
    digests.pop(str(current_agent), None)
    return False


def invalidate_repair_digests(context: dict, repaired_agent: int) -> None:
    """Invalidate before repair, including downstream summaries used by direct retries."""
    for section in ("context_digests", "_digest_hash_map"):
        values = _mapping(context.get(section))
        for key in list(values):
            target = key[0] if isinstance(key, tuple) else key
            try:
                target = int(target)
            except (TypeError, ValueError):
                continue
            if target == repaired_agent or repaired_agent in upstream_agent_numbers(target, context):
                values.pop(key, None)
        if section in context:
            context[section] = values
