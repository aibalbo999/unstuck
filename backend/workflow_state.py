"""Checkpoint-safe LangGraph state and adapters for analysis workflows."""

from __future__ import annotations

import copy
import json
from typing import Annotated, Any, TypedDict

from agent_state import AgentState
from rag_runtime import InMemoryRagIndex, RagChunk


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Merge parallel graph deltas without sharing mutable nested objects."""

    merged = copy.deepcopy(left or {})
    merged.update(copy.deepcopy(right or {}))
    return merged


def append_unique(left: list | None, right: list | None) -> list:
    """Append graph list deltas while de-duplicating stable items."""

    result = copy.deepcopy(left or [])
    seen = {_unique_marker(item) for item in result}
    for item in copy.deepcopy(right or []):
        marker = _unique_marker(item)
        if marker not in seen:
            result.append(item)
            seen.add(marker)
    return result


def _unique_marker(item: Any) -> str:
    if isinstance(item, dict) and item.get("id") is not None:
        return f"id:{item['id']}"
    return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)


class AgentGraphState(TypedDict, total=False):
    """JSON-compatible checkpoint schema for LangGraph execution.

    Process-local clients, callbacks, locks, checkpointers, compiled graphs,
    and in-memory indexes must stay outside this state.
    """

    run_id: str
    ticker: str
    company_name: str
    company_identity: dict[str, Any]
    pipeline_id: str
    raw_financial_data: dict[str, Any]
    provider_values: dict[str, list[dict[str, Any]]]
    normalized_financials: dict[str, Any]
    source_audit: Annotated[list[dict[str, Any]], append_unique]
    validation_issues: list[dict[str, Any]]
    circuit_breaker: dict[str, Any]
    peer_context: dict[str, Any]
    quant_metrics: dict[str, Any]
    tool_results: Annotated[dict[str, Any], merge_dicts]
    agent_reports: Annotated[dict[str, dict[str, Any]], merge_dicts]
    risk_flags: Annotated[list[dict[str, Any]], append_unique]
    execution_trace: Annotated[list[dict[str, Any]], append_unique]
    analyses: Annotated[dict[str, str], merge_dicts]
    structured_outputs: Annotated[dict[str, dict[str, Any]], merge_dicts]
    parsed: Annotated[dict[str, Any], merge_dicts]
    context_digests: Annotated[dict[str, str], merge_dicts]
    rag_context: Annotated[dict[str, str], merge_dicts]
    rag_status: dict[str, Any]
    blocking_issues: Annotated[list[str], append_unique]
    audit_repair_log: Annotated[list[str], append_unique]
    repair_attempt_counts: dict[str, int]
    repair_iteration_count: int
    final_audit: dict[str, Any]
    tear_sheet_summary: str
    report_cover: dict[str, Any]
    report_filename: str
    report_event: dict[str, Any]
    started_at: float
    total_time: float
    status: str
    retryable_error: dict[str, Any] | None


def agent_state_to_graph(state: AgentState, *, pipeline_id: str) -> AgentGraphState:
    """Serialize the domain ``AgentState`` into the checkpoint schema."""

    payload = copy.deepcopy(state.model_dump(mode="json"))
    payload["pipeline_id"] = str(pipeline_id)
    return payload


def agent_state_from_graph(state: AgentGraphState | dict[str, Any]) -> AgentState:
    """Validate the domain subset of a checkpoint state as ``AgentState``."""

    allowed_fields = set(AgentState.model_fields)
    domain_payload = {
        key: copy.deepcopy(value)
        for key, value in dict(state).items()
        if key in allowed_fields
    }
    return AgentState.model_validate(domain_payload)


def rag_index_to_payload(index: InMemoryRagIndex | None) -> dict[str, Any] | None:
    """Serialize an in-memory RAG index into JSON-compatible state."""

    if index is None:
        return None
    return {
        "metadata": copy.deepcopy(index.metadata),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "text": chunk.text,
                "metadata": copy.deepcopy(chunk.metadata),
                "embedding": copy.deepcopy(chunk.embedding),
            }
            for chunk in index.chunks
        ],
    }


def rag_index_from_payload(payload: dict[str, Any] | None) -> InMemoryRagIndex:
    """Rebuild an ephemeral in-memory RAG index from checkpoint payload."""

    payload = payload or {}
    chunks = [
        RagChunk(
            str(item.get("chunk_id") or ""),
            str(item.get("source") or ""),
            str(item.get("text") or ""),
            copy.deepcopy(item.get("metadata") or {}),
            copy.deepcopy(item.get("embedding")),
        )
        for item in payload.get("chunks", []) or []
        if isinstance(item, dict)
    ]
    return InMemoryRagIndex(chunks, metadata=copy.deepcopy(payload.get("metadata") or {}))
