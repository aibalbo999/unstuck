"""Deprecated compatibility facade for RAG runtime helpers.

Production code should import from ``rag_runtime``.
"""

from __future__ import annotations

import inspect
import warnings

from rag_runtime import (
    AGENT_RAG_QUERIES,
    INTERESTING_PATH_MARKERS,
    RECORD_TEXT_KEYS,
    InMemoryRagIndex,
    RagChunk,
    RagSearchResult,
    _agent_query as _agent_query_impl,
    _attach_vectors as _attach_vectors_impl,
    _chunk_document as _chunk_document_impl,
    _clip_text as _clip_text_impl,
    _cosine_similarity as _cosine_similarity_impl,
    _embedding_cache_key as _embedding_cache_key_impl,
    _embedding_config as _embedding_config_impl,
    _embedding_config_parts as _embedding_config_parts_impl,
    _extract_embeddings as _extract_embeddings_impl,
    _format_results as _format_results_impl,
    _get_cached_embedding as _get_cached_embedding_impl,
    _interesting_path as _interesting_path_impl,
    _lexical_score as _lexical_score_impl,
    _merge_embedding_vectors as _merge_embedding_vectors_impl,
    _normalize_whitespace as _normalize_whitespace_impl,
    _record_to_text as _record_to_text_impl,
    _set_cached_embedding as _set_cached_embedding_impl,
    _split_cached_embeddings as _split_cached_embeddings_impl,
    _tokenize_for_lexical as _tokenize_for_lexical_impl,
    build_chunks as build_chunks_impl,
    build_rag_index as build_rag_index_impl,
    build_rag_index_async as build_rag_index_async_impl,
    collect_rag_documents as collect_rag_documents_impl,
    embed_query as embed_query_impl,
    embed_query_async as embed_query_async_impl,
    ensure_agent_rag_context as ensure_agent_rag_context_impl,
    ensure_agent_rag_context_async as ensure_agent_rag_context_async_impl,
)


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"rag_service.{name} is deprecated; use rag_runtime instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _deprecated_function(name: str, func):
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(*args, **kwargs):
            _warn_deprecated(name)
            return await func(*args, **kwargs)

        return async_wrapper

    def wrapper(*args, **kwargs):
        _warn_deprecated(name)
        return func(*args, **kwargs)

    return wrapper


def _embed_query(query, rotator):
    _warn_deprecated("_embed_query")
    vector, _warnings = embed_query_impl(query, rotator)
    return vector


async def _embed_query_async(query, rotator):
    _warn_deprecated("_embed_query_async")
    vector, _warnings = await embed_query_async_impl(query, rotator)
    return vector


_agent_query = _deprecated_function("_agent_query", _agent_query_impl)
_attach_vectors = _deprecated_function("_attach_vectors", _attach_vectors_impl)
_chunk_document = _deprecated_function("_chunk_document", _chunk_document_impl)
_clip_text = _deprecated_function("_clip_text", _clip_text_impl)
_cosine_similarity = _deprecated_function("_cosine_similarity", _cosine_similarity_impl)
_embedding_cache_key = _deprecated_function("_embedding_cache_key", _embedding_cache_key_impl)
_embedding_config = _deprecated_function("_embedding_config", _embedding_config_impl)
_embedding_config_parts = _deprecated_function("_embedding_config_parts", _embedding_config_parts_impl)
_extract_embeddings = _deprecated_function("_extract_embeddings", _extract_embeddings_impl)
_format_results = _deprecated_function("_format_results", _format_results_impl)
_get_cached_embedding = _deprecated_function("_get_cached_embedding", _get_cached_embedding_impl)
_interesting_path = _deprecated_function("_interesting_path", _interesting_path_impl)
_lexical_score = _deprecated_function("_lexical_score", _lexical_score_impl)
_merge_embedding_vectors = _deprecated_function("_merge_embedding_vectors", _merge_embedding_vectors_impl)
_normalize_whitespace = _deprecated_function("_normalize_whitespace", _normalize_whitespace_impl)
_record_to_text = _deprecated_function("_record_to_text", _record_to_text_impl)
_set_cached_embedding = _deprecated_function("_set_cached_embedding", _set_cached_embedding_impl)
_split_cached_embeddings = _deprecated_function("_split_cached_embeddings", _split_cached_embeddings_impl)
_tokenize_for_lexical = _deprecated_function("_tokenize_for_lexical", _tokenize_for_lexical_impl)
build_chunks = _deprecated_function("build_chunks", build_chunks_impl)
build_rag_index = _deprecated_function("build_rag_index", build_rag_index_impl)
build_rag_index_async = _deprecated_function("build_rag_index_async", build_rag_index_async_impl)
collect_rag_documents = _deprecated_function("collect_rag_documents", collect_rag_documents_impl)
ensure_agent_rag_context = _deprecated_function("ensure_agent_rag_context", ensure_agent_rag_context_impl)
ensure_agent_rag_context_async = _deprecated_function("ensure_agent_rag_context_async", ensure_agent_rag_context_async_impl)
