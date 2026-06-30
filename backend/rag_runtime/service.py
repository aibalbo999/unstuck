"""Canonical RAG orchestration service."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from cache_store import get_cache_json, set_cache_json
from config import (
    AGENT_STEP_CACHE_ENABLED,
    AGENT_STEP_CACHE_SECONDS,
    EMBEDDING_MODEL,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_ENABLED,
    RAG_MAX_INDEX_CHUNKS,
    get_agent_rag_budget,
)
from data_trust_snapshot import sanitize_for_snapshot
from llm_client import KeyRotator

from .chunking import build_chunks
from .documents import hybrid_search, hybrid_search_async
from .embeddings import embed_index_chunks, embed_index_chunks_async, embed_query, embed_query_async
from .queries import _agent_query, _format_results
from .types import InMemoryRagIndex, RagChunk


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


def _data_snapshot_hash(data: dict[str, Any]) -> str:
    for key in ("data_snapshot_hash", "snapshot_hash", "content_hash"):
        value = data.get(key) if isinstance(data, dict) else None
        if str(value or "").strip():
            return str(value).strip()
    encoded = json.dumps(sanitize_for_snapshot(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "data:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _rag_index_cache_key(data: dict[str, Any]) -> str:
    key_parts = {
        "ticker": str((data or {}).get("ticker") or ""),
        "snapshot": _data_snapshot_hash(data or {}),
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": RAG_CHUNK_SIZE,
        "chunk_overlap": RAG_CHUNK_OVERLAP,
        "max_chunks": RAG_MAX_INDEX_CHUNKS,
    }
    encoded = json.dumps(key_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "rag_index:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _index_to_payload(index: InMemoryRagIndex) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "metadata": sanitize_for_snapshot(index.metadata),
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "source": chunk.source,
                "text": chunk.text,
                "metadata": sanitize_for_snapshot(chunk.metadata),
                "embedding": sanitize_for_snapshot(chunk.embedding),
            }
            for chunk in index.chunks
        ],
    }


def _index_from_payload(payload: object) -> InMemoryRagIndex | None:
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 0) != 1:
        return None
    chunks = []
    for item in payload.get("chunks", []) or []:
        if not isinstance(item, dict):
            continue
        chunks.append(RagChunk(
            chunk_id=str(item.get("chunk_id") or ""),
            source=str(item.get("source") or ""),
            text=str(item.get("text") or ""),
            metadata=dict(item.get("metadata") or {}),
            embedding=item.get("embedding") if isinstance(item.get("embedding"), list) else None,
        ))
    if not chunks:
        return None
    metadata = dict(payload.get("metadata") or {})
    metadata["cache_hit"] = True
    return InMemoryRagIndex(chunks, metadata=metadata)


def _get_cached_rag_index(data: dict[str, Any]) -> InMemoryRagIndex | None:
    if not AGENT_STEP_CACHE_ENABLED or AGENT_STEP_CACHE_SECONDS <= 0:
        return None
    try:
        return _index_from_payload(get_cache_json(_rag_index_cache_key(data)))
    except Exception:
        return None


def _store_cached_rag_index(data: dict[str, Any], index: InMemoryRagIndex) -> None:
    if not AGENT_STEP_CACHE_ENABLED or AGENT_STEP_CACHE_SECONDS <= 0:
        return
    try:
        set_cache_json(_rag_index_cache_key(data), _index_to_payload(index), AGENT_STEP_CACHE_SECONDS)
    except Exception:
        return


def build_rag_index(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Build an in-memory RAG index; if embedding fails, keep lexical chunks."""
    if not RAG_ENABLED:
        return None
    cached = _get_cached_rag_index(data)
    if cached is not None:
        return cached
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks, metadata={"warnings": []})
    _record_warnings(index.metadata, embed_index_chunks(chunks, data, rotator))
    _store_cached_rag_index(data, index)
    return index


async def build_rag_index_async(data: dict[str, Any], rotator: Optional[KeyRotator] = None) -> Optional[InMemoryRagIndex]:
    """Async RAG index builder for the analysis pipeline."""
    if not RAG_ENABLED:
        return None
    cached = _get_cached_rag_index(data)
    if cached is not None:
        return cached
    chunks = build_chunks(data)
    if not chunks:
        return None

    index = InMemoryRagIndex(chunks, metadata={"warnings": []})
    _record_warnings(index.metadata, await embed_index_chunks_async(chunks, data, rotator))
    _store_cached_rag_index(data, index)
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
