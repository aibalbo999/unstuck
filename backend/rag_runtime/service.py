"""Canonical RAG orchestration service."""

from __future__ import annotations

from typing import Any, Optional

from config import RAG_ENABLED, get_agent_rag_budget
from llm_client import KeyRotator

from .chunking import build_chunks
from .documents import hybrid_search, hybrid_search_async
from .embeddings import embed_index_chunks, embed_index_chunks_async, embed_query, embed_query_async
from .queries import _agent_query, _format_results
from .types import InMemoryRagIndex


def _record_warnings(metadata: dict[str, Any], warnings: list[str]) -> None:
    if not warnings:
        return
    existing = metadata.setdefault("warnings", [])
    for warning in warnings:
        if warning and warning not in existing:
            existing.append(warning)


def _copy_index_warnings_to_context(context: dict, index: InMemoryRagIndex) -> None:
    warnings = list((getattr(index, "metadata", {}) or {}).get("warnings") or [])
    if not warnings:
        return
    rag_status = context.setdefault("rag_status", {})
    existing = rag_status.setdefault("warnings", [])
    for warning in warnings:
        if warning not in existing:
            existing.append(warning)


def build_rag_index(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Build an in-memory RAG index; if embedding fails, keep lexical chunks."""
    if not RAG_ENABLED:
        return None
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks, metadata={"warnings": []})
    _record_warnings(index.metadata, embed_index_chunks(chunks, data, rotator))
    return index


async def build_rag_index_async(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Async RAG index builder for the analysis pipeline."""
    if not RAG_ENABLED:
        return None
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks, metadata={"warnings": []})
    _record_warnings(index.metadata, await embed_index_chunks_async(chunks, data, rotator))
    return index


def ensure_agent_rag_context(agent_num: int, context: dict, rotator: Optional[KeyRotator] = None) -> str:
    if not RAG_ENABLED:
        return ""
    rag_context = context.setdefault("rag_context", {})
    if agent_num in rag_context:
        return rag_context[agent_num]

    index = context.get("rag_index")
    if index is None:
        index = build_rag_index(context.get("data", {}) or {}, rotator)
        if index is not None:
            context["rag_index"] = index
    if not isinstance(index, InMemoryRagIndex) or not index.chunks:
        return ""

    _copy_index_warnings_to_context(context, index)
    query = _agent_query(agent_num, context.get("data", {}) or {})
    query_embedding, warnings = embed_query(query, rotator) if index.has_embeddings else (None, [])
    _record_warnings(index.metadata, warnings)
    _copy_index_warnings_to_context(context, index)
    max_chars, top_k = get_agent_rag_budget(agent_num)
    results = hybrid_search(
        index,
        query,
        query_embedding=query_embedding,
        candidate_k=max(20, top_k * 4),
        top_k=top_k,
        max_chars=max_chars,
    )
    formatted = _format_results(results, agent_num)
    if formatted:
        rag_context[agent_num] = formatted
    return formatted


async def ensure_agent_rag_context_async(agent_num: int, context: dict, rotator: Optional[KeyRotator] = None) -> str:
    if not RAG_ENABLED:
        return ""
    rag_context = context.setdefault("rag_context", {})
    if agent_num in rag_context:
        return rag_context[agent_num]

    index = context.get("rag_index")
    if index is None:
        index = await build_rag_index_async(context.get("data", {}) or {}, rotator)
        if index is not None:
            context["rag_index"] = index
    if not isinstance(index, InMemoryRagIndex) or not index.chunks:
        return ""

    _copy_index_warnings_to_context(context, index)
    query = _agent_query(agent_num, context.get("data", {}) or {})
    query_embedding, warnings = await embed_query_async(query, rotator) if index.has_embeddings else (None, [])
    _record_warnings(index.metadata, warnings)
    _copy_index_warnings_to_context(context, index)
    max_chars, top_k = get_agent_rag_budget(agent_num)
    results = await hybrid_search_async(
        index,
        query,
        query_embedding=query_embedding,
        candidate_k=max(20, top_k * 4),
        top_k=top_k,
        max_chars=max_chars,
    )
    formatted = _format_results(results, agent_num)
    if formatted:
        rag_context[agent_num] = formatted
    return formatted
