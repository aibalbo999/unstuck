"""RAG embedding cache and provider-call helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Optional

from google.genai import types

from cache_store import get_cache_json, set_cache_json
from config import EMBEDDING_MODEL, RAG_EMBEDDING_CACHE_SECONDS
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    embed_content,
    embed_content_async,
    estimate_text_tokens,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)
from runtime_events import classify_runtime_error

from .types import RagChunk


def _extract_embeddings(response) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None) or []
    vectors = []
    for embedding in embeddings:
        values = getattr(embedding, "values", None) or []
        vectors.append([float(value) for value in values])
    return vectors


def _embedding_config(task_type: str, title: str | None = None):
    kwargs = {"task_type": task_type}
    if title:
        kwargs["title"] = title
    return types.EmbedContentConfig(**kwargs)


def _embedding_config_parts(config) -> tuple[str, str]:
    return (
        str(getattr(config, "task_type", "") or ""),
        str(getattr(config, "title", "") or ""),
    )


def _embedding_cache_key(model_id: str, text: str, config) -> str:
    task_type, title = _embedding_config_parts(config)
    digest = sha256(
        json.dumps(
            {
                "model": model_id,
                "task_type": task_type,
                "title": title,
                "text": text,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8", "ignore")
    ).hexdigest()
    return f"rag_embedding:{digest}"


def _get_cached_embedding(model_id: str, text: str, config) -> Optional[list[float]]:
    if RAG_EMBEDDING_CACHE_SECONDS <= 0:
        return None
    try:
        cached = get_cache_json(_embedding_cache_key(model_id, text, config))
    except Exception:
        return None
    vector = cached.get("vector") if isinstance(cached, dict) else None
    if not isinstance(vector, list) or not vector:
        return None
    try:
        return [float(value) for value in vector]
    except (TypeError, ValueError):
        return None


def _set_cached_embedding(model_id: str, text: str, config, vector: list[float]) -> None:
    if RAG_EMBEDDING_CACHE_SECONDS <= 0 or not vector:
        return
    try:
        set_cache_json(
            _embedding_cache_key(model_id, text, config),
            {"vector": [float(value) for value in vector]},
            RAG_EMBEDDING_CACHE_SECONDS,
        )
    except Exception:
        return


def _split_cached_embeddings(model_id: str, texts: list[str], config):
    vectors: list[Optional[list[float]]] = [None] * len(texts)
    missing_indices = []
    missing_texts = []
    for index, text in enumerate(texts):
        cached = _get_cached_embedding(model_id, text, config)
        if cached:
            vectors[index] = cached
        else:
            missing_indices.append(index)
            missing_texts.append(text)
    return vectors, missing_indices, missing_texts


def _merge_embedding_vectors(
    vectors: list[Optional[list[float]]],
    missing_indices: list[int],
    missing_texts: list[str],
    fetched_vectors: list[list[float]],
    model_id: str,
    config,
) -> list[Optional[list[float]]]:
    for index, text, vector in zip(missing_indices, missing_texts, fetched_vectors):
        if vector:
            vectors[index] = vector
            _set_cached_embedding(model_id, text, config, vector)
    return vectors


def _attach_vectors(chunks: list[RagChunk], vectors: list[list[float]]) -> int:
    attached = 0
    for chunk, vector in zip(chunks, vectors):
        if vector:
            chunk.embedding = vector
            attached += 1
    return attached


def _embedding_warning(exc: Exception, scope: str) -> str:
    category = classify_runtime_error(exc, default="provider")
    if is_quota_or_rate_error(str(exc)):
        return f"RAG {scope} embedding quota/rate limit ({category}); using lexical retrieval: {describe_quota_or_rate_error(exc)[:120]}"
    if is_missing_model_error(str(exc)):
        return f"RAG {scope} embedding model unavailable ({category}); using lexical retrieval: {str(exc)[:120]}"
    return f"RAG {scope} embedding failed ({category}); using lexical retrieval: {str(exc)[:120]}"


def embed_index_chunks(chunks: list[RagChunk], data: dict, rotator: Optional[KeyRotator]) -> list[str]:
    if not isinstance(rotator, KeyRotator):
        return []

    api_key = None
    try:
        texts = [chunk.text for chunk in chunks]
        config = _embedding_config("RETRIEVAL_DOCUMENT", title=str(data.get("company_name") or data.get("ticker") or "stock"))
        vectors, missing_indices, missing_texts = _split_cached_embeddings(EMBEDDING_MODEL, texts, config)
        if missing_texts:
            estimated_tokens = estimate_text_tokens("\n\n".join(missing_texts))
            api_key = rotator.get_key(EMBEDDING_MODEL, estimated_tokens)
            response = embed_content(api_key, EMBEDDING_MODEL, missing_texts, config)
            vectors = _merge_embedding_vectors(
                vectors,
                missing_indices,
                missing_texts,
                _extract_embeddings(response),
                EMBEDDING_MODEL,
                config,
            )
        _attach_vectors(chunks, vectors)
        return []
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        return [_embedding_warning(exc, "document")]


async def embed_index_chunks_async(chunks: list[RagChunk], data: dict, rotator: Optional[KeyRotator]) -> list[str]:
    if not isinstance(rotator, KeyRotator):
        return []

    api_key = None
    try:
        texts = [chunk.text for chunk in chunks]
        config = _embedding_config("RETRIEVAL_DOCUMENT", title=str(data.get("company_name") or data.get("ticker") or "stock"))
        vectors, missing_indices, missing_texts = _split_cached_embeddings(EMBEDDING_MODEL, texts, config)
        if missing_texts:
            estimated_tokens = estimate_text_tokens("\n\n".join(missing_texts))
            api_key = await rotator.async_get_key(EMBEDDING_MODEL, estimated_tokens)
            response = await embed_content_async(api_key, EMBEDDING_MODEL, missing_texts, config)
            vectors = _merge_embedding_vectors(
                vectors,
                missing_indices,
                missing_texts,
                _extract_embeddings(response),
                EMBEDDING_MODEL,
                config,
            )
        _attach_vectors(chunks, vectors)
        return []
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        return [_embedding_warning(exc, "document")]


def embed_query(query: str, rotator: Optional[KeyRotator]) -> tuple[Optional[list[float]], list[str]]:
    if not isinstance(rotator, KeyRotator):
        return None, []
    api_key = None
    try:
        config = _embedding_config("RETRIEVAL_QUERY")
        cached = _get_cached_embedding(EMBEDDING_MODEL, query, config)
        if cached:
            return cached, []
        api_key = rotator.get_key(EMBEDDING_MODEL, estimate_text_tokens(query))
        response = embed_content(api_key, EMBEDDING_MODEL, query, config)
        vectors = _extract_embeddings(response)
        if vectors:
            _set_cached_embedding(EMBEDDING_MODEL, query, config, vectors[0])
            return vectors[0], []
        return None, []
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        if is_quota_or_rate_error(str(exc)) or is_missing_model_error(str(exc)):
            return None, []
        return None, [_embedding_warning(exc, "query")]


async def embed_query_async(query: str, rotator: Optional[KeyRotator]) -> tuple[Optional[list[float]], list[str]]:
    if not isinstance(rotator, KeyRotator):
        return None, []
    api_key = None
    try:
        config = _embedding_config("RETRIEVAL_QUERY")
        cached = _get_cached_embedding(EMBEDDING_MODEL, query, config)
        if cached:
            return cached, []
        api_key = await rotator.async_get_key(EMBEDDING_MODEL, estimate_text_tokens(query))
        response = await embed_content_async(api_key, EMBEDDING_MODEL, query, config)
        vectors = _extract_embeddings(response)
        if vectors:
            _set_cached_embedding(EMBEDDING_MODEL, query, config, vectors[0])
            return vectors[0], []
        return None, []
    except Exception as exc:
        if is_quota_or_rate_error(str(exc)) and api_key:
            rotator.penalize(api_key, EMBEDDING_MODEL, retry_delay_seconds(exc, default=60))
        if is_quota_or_rate_error(str(exc)) or is_missing_model_error(str(exc)):
            return None, []
        return None, [_embedding_warning(exc, "query")]
