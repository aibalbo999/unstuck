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
                await _save_record(node, record)
        except Exception:
            logging.getLogger(__name__).warning("Could not persist quality repair diagnostics for agent %s", agent_num)
        finally:
            _node.reset(token)


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
    await _save_record(node, record)


async def _save_record(node, record):
    if record == node["record"]:
        return
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"quality_draft": record}
    version = node["saver"].get_next_version(node["version"], None)
    checkpoint["channel_versions"] = {"quality_draft": version}
    checkpoint["updated_channels"] = ["quality_draft"]
    # This namespace never advances the graph or supplies a successful node delta.
    config = await node["saver"].aput(node["config"], checkpoint,
                                     {"source": "update", "step": -1, "parents": {}},
                                     checkpoint["channel_versions"])
    node["config"], node["version"] = config, version
    node["record"] = record
