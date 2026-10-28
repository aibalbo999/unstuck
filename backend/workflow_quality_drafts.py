"""Unvalidated drafts stored separately from successful graph-node checkpoints."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from langgraph.checkpoint.base import empty_checkpoint
from analysis_dependencies import upstream_input_hash

_session: ContextVar[tuple | None] = ContextVar("quality_draft_checkpoint_session", default=None)
_node: ContextVar[dict | None] = ContextVar("quality_draft_checkpoint_node", default=None)


@contextmanager
def checkpoint_draft_scope(saver, thread_id: str):
    token = _session.set((saver, thread_id))
    try:
        yield
    finally:
        _session.reset(token)


@asynccontextmanager
async def quality_draft_node(agent_num: int, state: dict, context: dict):
    session = _session.get()
    node = None
    if session is not None:
        saver, thread_id = session
        encoded = json.dumps({"state": state, "upstream_input_hash": upstream_input_hash(agent_num, context)},
                             sort_keys=True, ensure_ascii=False, default=str)
        fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": f"quality_draft/{agent_num}/{fingerprint}"}}
        saved = await saver.aget_tuple(config)
        record = None
        if saved is not None:
            record = saved.checkpoint["channel_values"].get("quality_draft")
            if not isinstance(record, dict) or not (
                record.get("status") == "unvalidated"
                and record.get("agent_num") == agent_num
                and record.get("input_fingerprint") == fingerprint
                and isinstance(record.get("text"), str) and record["text"].strip()
            ):
                raise RuntimeError("Invalid stored quality draft; refusing to regenerate or publish")
            context.setdefault("rag_context", {})[agent_num] = copy.deepcopy(record.get("rag_context", ""))
            context.setdefault("context_digests", {})[agent_num] = copy.deepcopy(record.get("context_digest", ""))
            if isinstance(record.get("repair_candidate_history"), dict):
                context.setdefault("repair_candidate_history", {})[str(agent_num)] = copy.deepcopy(record["repair_candidate_history"])
            if agent_num == 6 and 'agent_quality_retry_count' in record:
                count = record['agent_quality_retry_count']
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    raise RuntimeError('Invalid stored debate recovery count')
                counts = context.setdefault('agent_quality_retry_counts', {})
                counts[6] = max(int(counts.get(6, counts.get('6', 0)) or 0), count)
        version = saved.checkpoint.get("channel_versions", {}).get("quality_draft") if saved else None
        node = {"saver": saver, "config": saved.config if saved else config, "record": record, "version": version,
                "agent_num": agent_num, "input_fingerprint": fingerprint}
    token = _node.set(node)
    try:
        yield
    finally:
        try:
            if node is not None and node["record"] is not None:
                record = copy.deepcopy(node["record"])
                record["repair_candidate_history"] = _agent_value(context, "repair_candidate_history", agent_num)
                if agent_num == 6:
                    record['agent_quality_retry_count'] = _agent_value(context, 'agent_quality_retry_counts', 6, 0)
                await _save_record(node, record)
        except Exception:
            logging.getLogger(__name__).warning("Could not persist quality repair diagnostics for agent %s", agent_num)
        finally:
            _node.reset(token)


def _audit_metadata(context: dict) -> dict:
    from agent_runtime.repair_transaction import REPAIR_METADATA_FIELDS

    return {key: copy.deepcopy(context[key])
            for key in (*REPAIR_METADATA_FIELDS, "repair_iteration_count") if key in context}


def _audit_fingerprint(value) -> str:
    from workflow_context import copy_json

    encoded = json.dumps(copy_json(value), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@asynccontextmanager
async def final_audit_metadata(state: dict, context: dict):
    """Persist only spent repair metadata, never a successful graph-node delta."""
    from agent_runtime.deferred import AgentDeferredError

    session = _session.get()
    if session is None:
        yield
        return
    saver, thread_id = session
    fingerprint = _audit_fingerprint({
        "thread_id": thread_id, "run_id": state.get("run_id"),
        "pipeline_id": context.get("pipeline_id"),
        "prompt_version": context.get("prompt_version"),
        "prompt_fingerprint": context.get("prompt_fingerprint"),
        "data": context.get("data"),
        "accepted": {key: state.get(key) for key in (
            "analyses", "structured_outputs", "analysis_provenance", "invalidated_agents",
            "market_context_contract_version", "market_context_manifests", "position_sizing_context",
            "trade_source_evidence", "context_digests", "rag_context",
        )},
    })
    # Identity drift must find and reject the existing job receipt, not open a new budget.
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "final_audit_metadata"}}
    saved = await saver.aget_tuple(config)
    baseline_hash = _audit_fingerprint(_audit_metadata(context))
    if saved is not None:
        record = saved.checkpoint["channel_values"].get("final_audit_metadata")
        if not isinstance(record, dict) or not (
            record.get("version") == 1 and record.get("input_fingerprint") == fingerprint
            and record.get("status") == "ready" and isinstance(record.get("metadata"), dict)
            and record["metadata"] == _audit_metadata(record["metadata"])
            and record.get("metadata_hash") == _audit_fingerprint(record["metadata"])
            and baseline_hash in (record.get("baseline_hash"), record.get("metadata_hash"))
        ):
            raise RuntimeError("Uncertain final-audit repair metadata; refusing to reset budget")
        context.update(copy.deepcopy(record["metadata"]))
    node = {"saver": saver, "config": saved.config if saved else config,
            "version": saved.checkpoint.get("channel_versions", {}).get("final_audit_metadata") if saved else None,
            "record": None}

    async def save(status):
        metadata = _audit_metadata(context)
        record = {"version": 1, "status": status, "input_fingerprint": fingerprint,
                  "baseline_hash": baseline_hash, "metadata": metadata,
                  "metadata_hash": _audit_fingerprint(metadata)}
        await _save_record(node, record, channel="final_audit_metadata")

    # A crash or failed post-call write must not reopen the same budget on resume.
    await save("running")
    try:
        yield
    except AgentDeferredError:
        await save("ready")
        raise
    else:
        await save("ready")


def _agent_value(context: dict, section: str, agent_num: int, default=None):
    values = context.get(section) or {}
    return copy.deepcopy(values.get(agent_num, values.get(str(agent_num), default)))


def has_checkpointed_quality_draft() -> bool:
    node = _node.get()
    return node is not None and node["record"] is not None


async def initial_or_checkpointed_draft(agent_num, data, context, rotator, generate):
    node = _node.get()
    if node is not None and node["agent_num"] != agent_num:
        raise RuntimeError("Quality draft belongs to a different agent")
    if node is not None and (record := node["record"]) is not None:
        manifests = context.setdefault("market_context_manifests", {})
        manifests.pop(agent_num, None)
        manifests.pop(str(agent_num), None)
        if isinstance(record.get("market_context_manifest"), dict):
            manifests[agent_num] = copy.deepcopy(record["market_context_manifest"])
        if agent_num == 7:
            context.pop("_research_completion_receipt", None)
            context.pop("_research_incomplete_fields", None)
            receipt = record.get("research_completion_receipt")
            if isinstance(receipt, dict) and receipt.get("version") == 1:
                context["_research_completion_receipt"] = copy.deepcopy(receipt)
        if agent_num == 24:
            context.pop("_trade_completion_receipt", None)
            receipt = record.get("trade_completion_receipt")
            if isinstance(receipt, dict) and receipt.get("version") == 1:
                context["_trade_completion_receipt"] = copy.deepcopy(receipt)
            context.pop("_trade_source_manifest", None)
            trade_manifest = record.get("trade_source_manifest")
            from trade_source_contract import SUPPORTED_VERSIONS
            if isinstance(trade_manifest, dict) and trade_manifest.get("version") in SUPPORTED_VERSIONS:
                # The draft namespace already binds full input/upstream fingerprint.
                context["_trade_source_manifest"] = copy.deepcopy(trade_manifest)
        outputs = context.setdefault("structured_outputs", {})
        outputs.pop(agent_num, None)
        outputs.pop(str(agent_num), None)
        if record.get("structured_output") is not None:
            outputs[agent_num] = copy.deepcopy(record["structured_output"])
        return record["text"]

    result = await generate(agent_num, data, context, rotator)
    await checkpoint_unvalidated_draft(agent_num, result, context)
    return result


async def checkpoint_unvalidated_draft(agent_num: int, result: str, context: dict) -> None:
    from agent_runtime.routing import is_agent_execution_failure

    node = _node.get()
    if node is None or not isinstance(result, str) or not result.strip() or is_agent_execution_failure(result):
        return
    if node["agent_num"] != agent_num:
        raise RuntimeError("Quality draft belongs to a different agent")
    record = {
        "status": "unvalidated", "agent_num": agent_num,
        "input_fingerprint": node["input_fingerprint"], "text": result,
        "structured_output": _agent_value(context, "structured_outputs", agent_num),
        "market_context_manifest": _agent_value(context, "market_context_manifests", agent_num),
        "rag_context": _agent_value(context, "rag_context", agent_num, ""),
        "context_digest": _agent_value(context, "context_digests", agent_num, ""),
    }
    if agent_num == 24:
        record["trade_source_manifest"] = copy.deepcopy(context.get("_trade_source_manifest"))
        record["trade_completion_receipt"] = copy.deepcopy(context.get("_trade_completion_receipt"))
    if agent_num == 7:
        record["research_completion_receipt"] = copy.deepcopy(context.get("_research_completion_receipt"))
    record["repair_candidate_history"] = _agent_value(context, "repair_candidate_history", agent_num)
    if agent_num == 6:
        record['agent_quality_retry_count'] = _agent_value(context, 'agent_quality_retry_counts', 6, 0)
    await _save_record(node, record)


async def _save_record(node, record, *, channel="quality_draft"):
    if record == node["record"]:
        return
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {channel: record}
    version = node["saver"].get_next_version(node["version"], None)
    checkpoint["channel_versions"] = {channel: version}
    checkpoint["updated_channels"] = [channel]
    # This namespace never advances the graph or supplies a successful node delta.
    config = await node["saver"].aput(node["config"], checkpoint,
                                     {"source": "update", "step": -1, "parents": {}},
                                     checkpoint["channel_versions"])
    node["config"], node["version"] = config, version
    node["record"] = record
