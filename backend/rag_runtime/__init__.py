"""Canonical RAG runtime package."""

from .chunking import _chunk_document, build_chunks
from .documents import (
    INTERESTING_PATH_MARKERS,
    RECORD_TEXT_KEYS,
    _clip_text,
    _interesting_path,
    _normalize_whitespace,
    _record_to_text,
    collect_rag_documents,
)
from .embeddings import (
    _attach_vectors,
    _embedding_cache_key,
    _embedding_config,
    _embedding_config_parts,
    _extract_embeddings,
    _get_cached_embedding,
    _merge_embedding_vectors,
    _set_cached_embedding,
    _split_cached_embeddings,
    embed_index_chunks,
    embed_index_chunks_async,
    embed_query,
    embed_query_async,
)
from .queries import AGENT_RAG_QUERIES, _agent_query, _format_results
from .service import build_rag_index, build_rag_index_async, ensure_agent_rag_context, ensure_agent_rag_context_async
from .types import InMemoryRagIndex, RagChunk, RagSearchResult, _cosine_similarity, _lexical_score, _tokenize_for_lexical

__all__ = [
    "AGENT_RAG_QUERIES",
    "INTERESTING_PATH_MARKERS",
    "InMemoryRagIndex",
    "RECORD_TEXT_KEYS",
    "RagChunk",
    "RagSearchResult",
    "_agent_query",
    "_attach_vectors",
    "_chunk_document",
    "_clip_text",
    "_cosine_similarity",
    "_embedding_cache_key",
    "_embedding_config",
    "_embedding_config_parts",
    "_extract_embeddings",
    "_format_results",
    "_get_cached_embedding",
    "_interesting_path",
    "_lexical_score",
    "_merge_embedding_vectors",
    "_normalize_whitespace",
    "_record_to_text",
    "_set_cached_embedding",
    "_split_cached_embeddings",
    "_tokenize_for_lexical",
    "build_chunks",
    "build_rag_index",
    "build_rag_index_async",
    "collect_rag_documents",
    "embed_index_chunks",
    "embed_index_chunks_async",
    "embed_query",
    "embed_query_async",
    "ensure_agent_rag_context",
    "ensure_agent_rag_context_async",
]
