"""RAG data types and in-memory search implementation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Optional

from config import RAG_MAX_CHUNKS_PER_AGENT, RAG_MAX_CONTEXT_CHARS

from .documents import _clip_text


@dataclass
class RagChunk:
    chunk_id: str
    source: str
    text: str
    metadata: dict[str, Any]
    embedding: Optional[list[float]] = None


@dataclass
class RagSearchResult:
    chunk: RagChunk
    score: float


class InMemoryRagIndex:
    """Small local vector store; cosine search when embeddings exist, lexical otherwise."""

    def __init__(self, chunks: list[RagChunk], metadata: dict[str, Any] | None = None):
        self.chunks = chunks
        self.metadata = metadata or {}

    @property
    def has_embeddings(self) -> bool:
        return any(chunk.embedding for chunk in self.chunks)

    def search(
        self,
        query: str,
        query_embedding: Optional[list[float]] = None,
        top_k: int = RAG_MAX_CHUNKS_PER_AGENT,
        max_chars: int = RAG_MAX_CONTEXT_CHARS,
    ) -> list[RagSearchResult]:
        if not self.chunks:
            return []

        scored = []
        for chunk in self.chunks:
            if query_embedding and chunk.embedding:
                score = _cosine_similarity(query_embedding, chunk.embedding)
            else:
                score = _lexical_score(query, chunk.text, chunk.source)
            scored.append(RagSearchResult(chunk=chunk, score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        selected: list[RagSearchResult] = []
        used_chars = 0
        for item in scored:
            if len(selected) >= max(1, top_k):
                break
            if item.score <= 0 and selected:
                break
            remaining = max_chars - used_chars
            if remaining <= 200:
                break
            clipped_text = _clip_text(item.chunk.text, remaining)
            selected.append(RagSearchResult(
                chunk=RagChunk(
                    chunk_id=item.chunk.chunk_id,
                    source=item.chunk.source,
                    text=clipped_text,
                    metadata=item.chunk.metadata,
                    embedding=item.chunk.embedding,
                ),
                score=item.score,
            ))
            used_chars += len(clipped_text) + 120
        return selected


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _tokenize_for_lexical(text: str) -> list[str]:
    lowered = str(text or "").lower()
    latin = re.findall(r"[a-z0-9][a-z0-9_./+-]{1,}", lowered)
    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    return latin + cjk_terms


def _lexical_score(query: str, text: str, source: str = "") -> float:
    query_terms = set(_tokenize_for_lexical(query))
    if not query_terms:
        return 0.0
    haystack = f"{source}\n{text}".lower()
    return float(sum(1 for term in query_terms if term in haystack))
