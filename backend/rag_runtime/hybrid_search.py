"""Hybrid RAG retrieval and reranking primitives."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HybridSearchConfig:
    """Controls two-stage retrieval before LLM context formatting."""

    candidate_k: int = 20
    top_k: int = 5
    dense_weight: float = 0.65
    keyword_weight: float = 0.35
    rerank_timeout_seconds: float = 3.0


class Reranker:
    """Async cross-encoder reranker interface."""

    async def rerank(self, query: str, results: Sequence[Any], top_k: int = 5) -> list[Any]:
        return list(results)[: max(1, top_k)]


class CrossEncoderReranker(Reranker):
    """Reranker adapter for async or sync cross-encoder scoring callbacks."""

    def __init__(
        self,
        scorer: Callable[[str, Sequence[str]], Sequence[float] | Awaitable[Sequence[float]]],
        *,
        timeout_seconds: float = 3.0,
    ):
        self.scorer = scorer
        self.timeout_seconds = max(float(timeout_seconds), 0.1)

    async def rerank(self, query: str, results: Sequence[Any], top_k: int = 5) -> list[Any]:
        texts = [item.chunk.text for item in results]
        maybe_scores = self.scorer(query, texts)
        scores = await asyncio.wait_for(maybe_scores, timeout=self.timeout_seconds) if isinstance(maybe_scores, Awaitable) else maybe_scores
        paired = [(float(score), item) for score, item in zip(scores, results)]
        paired.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _score, item in paired[: max(1, top_k)]]


async def hybrid_search_async(
    index: Any,
    query: str,
    *,
    query_embedding: list[float] | None = None,
    candidate_k: int = 20,
    top_k: int = 5,
    max_chars: int | None = None,
    reranker: Reranker | None = None,
    dense_weight: float = 0.65,
    keyword_weight: float = 0.35,
) -> list[Any]:
    """Run BM25 + dense retrieval, rerank top candidates, return clipped Top-K."""
    from .types import RagChunk, RagSearchResult, _cosine_similarity

    chunks = list(getattr(index, "chunks", []) or [])
    if not chunks:
        return []
    config = HybridSearchConfig(
        candidate_k=max(1, int(candidate_k or 20)),
        top_k=max(1, min(int(top_k or 5), 5)),
        dense_weight=max(float(dense_weight), 0.0),
        keyword_weight=max(float(keyword_weight), 0.0),
    )
    keyword_scores = _bm25_scores(query, [chunk.text for chunk in chunks], [chunk.source for chunk in chunks])
    dense_scores = [
        _cosine_similarity(query_embedding, chunk.embedding) if query_embedding and chunk.embedding else 0.0
        for chunk in chunks
    ]
    keyword_norm = _normalize_scores(keyword_scores)
    dense_norm = _normalize_scores(dense_scores)
    weight_total = max(config.dense_weight + config.keyword_weight, 0.0001)

    candidates: list[RagSearchResult] = []
    for idx, chunk in enumerate(chunks):
        score = (config.dense_weight * dense_norm[idx] + config.keyword_weight * keyword_norm[idx]) / weight_total
        metadata = dict(chunk.metadata or {})
        metadata["hybrid_scores"] = {
            "dense": round(dense_scores[idx], 6),
            "keyword": round(keyword_scores[idx], 6),
            "combined": round(score, 6),
        }
        candidates.append(RagSearchResult(
            chunk=RagChunk(chunk.chunk_id, chunk.source, chunk.text, metadata, chunk.embedding),
            score=score,
        ))

    candidates.sort(key=lambda item: item.score, reverse=True)
    top_candidates = candidates[: config.candidate_k]
    top_candidates = await reranker.rerank(query, top_candidates, top_k=config.top_k) if reranker else top_candidates[: config.top_k]
    return _clip_search_results(top_candidates, max_chars=max_chars)


def hybrid_search(
    index: Any,
    query: str,
    *,
    query_embedding: list[float] | None = None,
    candidate_k: int = 20,
    top_k: int = 5,
    max_chars: int | None = None,
    dense_weight: float = 0.65,
    keyword_weight: float = 0.35,
) -> list[Any]:
    """Synchronous hybrid retrieval without external reranker calls."""
    return asyncio.run(hybrid_search_async(
        index,
        query,
        query_embedding=query_embedding,
        candidate_k=candidate_k,
        top_k=top_k,
        max_chars=max_chars,
        reranker=None,
        dense_weight=dense_weight,
        keyword_weight=keyword_weight,
    ))


def _bm25_scores(query: str, texts: Sequence[str], sources: Sequence[str] | None = None) -> list[float]:
    from .types import _tokenize_for_lexical

    query_terms = _tokenize_for_lexical(query)
    if not query_terms:
        return [0.0 for _text in texts]
    docs = [_tokenize_for_lexical(f"{source}\n{text}") for source, text in zip(sources or ["" for _text in texts], texts)]
    avg_len = sum(len(doc) for doc in docs) / max(len(docs), 1)
    document_frequency: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    scores: list[float] = []
    for doc in docs:
        term_counts = {term: doc.count(term) for term in set(doc)}
        scores.append(sum(_bm25_term_score(term, term_counts, len(doc), avg_len, len(docs), document_frequency) for term in query_terms))
    return scores


def _bm25_term_score(term: str, counts: dict[str, int], doc_len: int, avg_len: float, doc_count: int, df: dict[str, int]) -> float:
    frequency = counts.get(term, 0)
    if frequency <= 0:
        return 0.0
    k1 = 1.5
    b = 0.75
    idf = math.log(1 + (doc_count - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
    denominator = frequency + k1 * (1 - b + b * doc_len / max(avg_len, 1.0))
    return idf * (frequency * (k1 + 1)) / max(denominator, 0.0001)


def _normalize_scores(scores: Sequence[float]) -> list[float]:
    if not scores:
        return []
    minimum = min(scores)
    maximum = max(scores)
    if maximum == minimum:
        return [1.0 if maximum > 0 else 0.0 for _score in scores]
    return [(score - minimum) / (maximum - minimum) for score in scores]


def _clip_search_results(results: Sequence[Any], *, max_chars: int | None) -> list[Any]:
    if max_chars is None:
        return list(results)
    from .documents import _clip_text
    from .types import RagChunk, RagSearchResult

    selected: list[RagSearchResult] = []
    used_chars = 0
    for item in results:
        remaining = max_chars - used_chars
        if remaining <= 200:
            break
        clipped_text = _clip_text(item.chunk.text, remaining)
        selected.append(RagSearchResult(
            chunk=RagChunk(item.chunk.chunk_id, item.chunk.source, clipped_text, item.chunk.metadata, item.chunk.embedding),
            score=item.score,
        ))
        used_chars += len(clipped_text) + 120
    return selected
