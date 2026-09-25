"""Deterministic cache for reusable agent step outputs."""

from __future__ import annotations

import hashlib
import json
import copy
from typing import Any

from cache_store import get_cache_json, set_cache_json
from llm_cache_policy import candidate_cache_read_allowed
from config import AGENT_STEP_CACHE_ENABLED, AGENT_STEP_CACHE_SECONDS
from data_trust_snapshot import sanitize_for_snapshot
from analysis_dependencies import upstream_input_hash
from market_context_manifest import CONTRACT_VERSION, FINAL_AGENTS, clear_market_context_output, manifest_matches_input, prompt_fingerprint


PROMPT_VERSION_DEFAULT = "runtime_rules:unversioned"
# Step outputs are already normalized/rendered. Bump when the listed roles'
# system/generation or output contract changes even if their user prompt does not.
AGENT_OUTPUT_CONTRACT_VERSION = "agent-output:role-evidence:v4"
_OUTPUT_CONTRACT_AGENTS = frozenset({3, 7, 12, 16, 18, 19, 20, 21})


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
        "upstream_input_hash": upstream_input_hash(agent_num, context),
        "market_context_contract_version": context.get("market_context_contract_version"),
    }
    if agent_num in {23, 24}:
        key_parts["institutional_evidence_contract"] = "typed-flow:v2"
    if agent_num == 24:
        key_parts["trade_source_contract_version"] = "trade-sources:v3-completion:v9"
        from trade_financial_risk import FINANCIAL_RISK_POLICY_VERSION
        key_parts["financial_risk_policy_version"] = FINANCIAL_RISK_POLICY_VERSION
    if agent_num in _OUTPUT_CONTRACT_AGENTS:
        key_parts["output_contract_version"] = AGENT_OUTPUT_CONTRACT_VERSION
    if agent_num == 7:
        from research_quote_fidelity import POLICY
        key_parts["research_quote_policy"] = POLICY
    if agent_num == 19:
        key_parts["no_position_contract_version"] = "explicit-cover-stop:v2-research-wording"
        key_parts["short_setup_feedback_contract"] = "schema-price-fields:v1"
    encoded = json.dumps(key_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "agent_step:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_cached_agent_step(cache_key: str) -> dict | None:
    if not candidate_cache_read_allowed("step") or not AGENT_STEP_CACHE_ENABLED:
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
    if agent_num == 24 and not _structured_output_for_agent(context, agent_num):
        return  # Incomplete drafts must reach the bounded structured retry, not its cache.
    payload = {
        "schema_version": 1,
        "agent_num": agent_num,
        "model_id": str(model_id or ""),
        "text": str(text or ""),
        "structured_output": _structured_output_for_agent(context, agent_num),
    }
    if agent_num in FINAL_AGENTS and context.get("market_context_contract_version") == CONTRACT_VERSION:
        manifests = context.get("market_context_manifests", {})
        payload["market_context_manifest"] = copy.deepcopy(manifests.get(agent_num, manifests.get(str(agent_num))))
    if agent_num == 24:
        payload["trade_source_manifest"] = copy.deepcopy(context.get("_trade_source_manifest"))
        payload["trade_completion_receipt"] = copy.deepcopy(context.get("_trade_completion_receipt"))
    try:
        set_cache_json(cache_key, payload, AGENT_STEP_CACHE_SECONDS)
    except Exception:
        return


def restore_cached_agent_step(context: dict, agent_num: int, cached: dict) -> str:
    clear_market_context_output(context, agent_num)
    if agent_num == 24:
        context.pop("_trade_source_manifest", None)
        context.pop("_trade_completion_receipt", None)
        if not _cached_trade_matches_input(context, cached):
            outputs = context.setdefault("structured_outputs", {})
            outputs.pop(24, None)
            outputs.pop("24", None)
            return ""
        context["_trade_source_manifest"] = copy.deepcopy(cached["trade_source_manifest"])
        receipt = cached.get("trade_completion_receipt")
        if isinstance(receipt, dict):
            context["_trade_completion_receipt"] = copy.deepcopy(receipt)
    structured = cached.get("structured_output")
    if isinstance(structured, dict):
        context.setdefault("structured_outputs", {})[agent_num] = copy.deepcopy(structured)
    manifest = cached.get("market_context_manifest")
    if isinstance(manifest, dict):
        context.setdefault("market_context_manifests", {})[agent_num] = copy.deepcopy(manifest)
    stats = context.setdefault("agent_step_cache", {"hits": 0, "misses": 0})
    stats["hits"] = int(stats.get("hits") or 0) + 1
    return str(cached.get("text") or "")


def cached_market_context_matches(context: dict, agent_num: int, cached: dict, prompt: str) -> bool:
    if agent_num == 24:
        return (_cached_trade_matches_input(context, cached)
                and cached.get("trade_source_manifest") == context.get("_trade_source_manifest"))
    if agent_num not in FINAL_AGENTS or context.get("market_context_contract_version") != CONTRACT_VERSION:
        return True
    manifest = cached.get("market_context_manifest")
    attempts = context.get("_market_context_attempt_manifests", {})
    expected = attempts.get(agent_num, attempts.get(str(agent_num)))
    return (manifest_matches_input(manifest, context.get("data", {}), agent_num)
            and manifest.get("prompt_hash") == prompt_fingerprint(prompt) and manifest == expected)


def _cached_trade_matches_input(context, cached):
    from workflow_trade_evidence import trade_manifest_matches_input
    from llm_completion_provenance import completion_is_incomplete

    manifest = cached.get("trade_source_manifest")
    output = cached.get("structured_output")
    assessment = output.get("source_assessment") if isinstance(output, dict) else None
    receipt = cached.get("trade_completion_receipt")
    if (isinstance(receipt, dict) and completion_is_incomplete(receipt.get("diagnostics"))
            or isinstance(assessment, dict) and completion_is_incomplete(assessment.get("output_completion"))):
        return False
    return (trade_manifest_matches_input(manifest, context.get("data", {}))
            and isinstance(assessment, dict)
            and assessment.get("source_fingerprint") == manifest.get("fingerprint"))


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
