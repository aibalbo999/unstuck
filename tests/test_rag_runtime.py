import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import rag_runtime  # noqa: E402
import rag_runtime.chunking as chunking  # noqa: E402
import rag_runtime.documents as rag_documents  # noqa: E402
import rag_runtime.embeddings as embeddings  # noqa: E402
import rag_runtime.service as rag_service  # noqa: E402
import cache_store  # noqa: E402
from cache_backends import InMemoryCache  # noqa: E402
from llm_client import KeyRotator  # noqa: E402


class FakeRotator(KeyRotator):
    def __init__(self):
        self.penalties = []

    def get_key(self, model, estimated_tokens=0):
        return "fake-key"

    async def async_get_key(self, model, estimated_tokens=0):
        return "fake-key"

    def penalize(self, key, model, wait_seconds=60):
        self.penalties.append((key, model, wait_seconds))


def _embedding_response(*vectors):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=list(vector)) for vector in vectors])


def test_document_collection_keeps_long_or_interesting_text_and_dedupes(monkeypatch):
    monkeypatch.setattr(rag_runtime.documents, "RAG_MIN_SOURCE_CHARS", 80)
    long_text = "revenue margin cash flow " * 8
    data = {
        "tiny": "short",
        "filing": "短法說",
        "notes": [long_text, long_text],
    }

    documents = rag_runtime.collect_rag_documents(data)

    assert {doc["source"] for doc in documents} == {"data.filing", "data.notes[0]", "data.notes[1]"}
    assert all(doc["text"] for doc in documents)


def test_chunking_stable_ids_and_max_chunks(monkeypatch):
    monkeypatch.setattr(chunking, "RAG_MAX_INDEX_CHUNKS", 1)
    data = {"transcript": "alpha beta gamma " * 80, "news": "delta epsilon " * 80}

    chunks = rag_runtime.build_chunks(data)
    direct = rag_runtime._chunk_document("data.transcript", data["transcript"])
    repeated = rag_runtime._chunk_document("data.transcript", data["transcript"])

    assert len(chunks) == 1
    assert direct[0].chunk_id == repeated[0].chunk_id


def test_markdown_aware_chunker_preserves_header_sections_and_tables():
    markdown = """# 2025 Annual Report

Opening summary.

## Revenue

| Month | Revenue |
| --- | ---: |
| Jan | 100 |
| Feb | 120 |

Revenue commentary stays with the table.

## EPS

EPS commentary for the same filing.
"""

    chunks = chunking.MarkdownAwareChunker(chunk_size=220, overlap=0).chunk("annual.md", markdown)

    revenue_chunk = next(item for item in chunks if item.metadata.get("heading") == "Revenue")
    assert "## Revenue" in revenue_chunk.text
    assert "| Jan | 100 |" in revenue_chunk.text
    assert "Revenue commentary stays with the table." in revenue_chunk.text
    assert revenue_chunk.metadata["headers"] == ["2025 Annual Report", "Revenue"]
    assert all("| Month | Revenue |" not in item.text or "| Feb | 120 |" in item.text for item in chunks)


def test_embedding_cache_key_and_query_cache_write(monkeypatch):
    stored = {}
    monkeypatch.setattr(embeddings, "get_cache_json", lambda key: stored.get(key))
    monkeypatch.setattr(embeddings, "set_cache_json", lambda key, value, ttl: stored.setdefault(key, value))
    monkeypatch.setattr(embeddings, "embed_content", lambda *args: _embedding_response([0.1, 0.2]))

    config = embeddings._embedding_config("RETRIEVAL_QUERY")
    key = embeddings._embedding_cache_key("hello", "m", "2330")
    legacy_key = embeddings._embedding_cache_key("m", "hello", config)
    vector, warnings = embeddings.embed_query("hello", FakeRotator())

    assert key.startswith("rag_emb:2330:m:")
    assert legacy_key.startswith("rag_emb::m:")
    assert vector == [0.1, 0.2]
    assert warnings == []
    assert any(value == {"vector": [0.1, 0.2]} for value in stored.values())


def test_embedding_cache_key_ignores_run_metadata_and_changes_with_content():
    first = rag_runtime._embedding_cache_key("test content", "gemini-embedding-2", "2330")
    second = rag_runtime._embedding_cache_key("test content", "gemini-embedding-2", "2330")
    different = rag_runtime._embedding_cache_key("different content", "gemini-embedding-2", "2330")

    assert first == second
    assert first != different
    assert "run" not in first
    assert "job" not in first


def test_build_index_embedding_failure_falls_back_without_print(monkeypatch, capsys):
    monkeypatch.setattr(embeddings, "embed_content", lambda *args: (_ for _ in ()).throw(RuntimeError("embedding down")))
    data = {"ticker": "AAPL", "transcript": "margin pressure downgrade warning " * 40}

    index = rag_runtime.build_rag_index(data, FakeRotator())

    captured = capsys.readouterr()
    assert captured.out == ""
    assert index is not None
    assert index.has_embeddings is False
    assert "embedding down" in index.metadata["warnings"][0]


def test_async_build_index_uses_cached_embeddings(monkeypatch):
    calls = {"api": 0}
    monkeypatch.setattr(embeddings, "_get_cached_embedding", lambda model, text, config: [0.3, 0.4])

    async def fail_api(*args):
        calls["api"] += 1
        raise AssertionError("should not call external embedding")

    monkeypatch.setattr(embeddings, "embed_content_async", fail_api)

    index = asyncio.run(rag_runtime.build_rag_index_async({"transcript": "growth demand catalyst " * 50}, FakeRotator()))

    assert calls["api"] == 0
    assert index.has_embeddings is True


def test_build_index_reuses_cached_index_for_same_data_snapshot(monkeypatch):
    calls = {"embedding": 0}

    def fake_embed_index_chunks(chunks, data, rotator):
        calls["embedding"] += 1
        for chunk in chunks:
            chunk.embedding = [0.2, 0.8]
        return []

    try:
        cache_store.set_cache_backend(InMemoryCache())
        monkeypatch.setattr(rag_service, "embed_index_chunks", fake_embed_index_chunks)
        data = {
            "ticker": "2330.TW",
            "data_snapshot_hash": "snapshot-2026-06-30",
            "transcript": "AI server demand margin expansion " * 80,
        }

        first = rag_runtime.build_rag_index(data, FakeRotator())
        second = rag_runtime.build_rag_index(dict(data), FakeRotator())

        assert first is not None
        assert second is not None
        assert calls["embedding"] == 1
        assert first.chunks[0].chunk_id == second.chunks[0].chunk_id
        assert second.has_embeddings is True
    finally:
        cache_store.reset_cache_store_for_tests()


def test_vector_and_lexical_search_preserve_order_and_truncation():
    index = rag_runtime.InMemoryRagIndex([
        rag_runtime.RagChunk("a", "source.a", "alpha " * 80, {}, [1.0, 0.0]),
        rag_runtime.RagChunk("b", "source.b", "beta " * 80, {}, [0.0, 1.0]),
    ])

    vector_results = index.search("anything", query_embedding=[1.0, 0.0], top_k=1, max_chars=260)
    lexical_results = index.search("beta", top_k=1, max_chars=1000)

    assert vector_results[0].chunk.chunk_id == "a"
    assert "RAG 片段截斷" in vector_results[0].chunk.text
    assert lexical_results[0].chunk.chunk_id == "b"


def test_hybrid_search_reranks_top_twenty_candidates_to_top_five():
    chunks = [
        rag_runtime.RagChunk(f"c{i}", "source", f"generic filing note {i}", {}, [0.9, 0.1])
        for i in range(18)
    ]
    chunks.extend([
        rag_runtime.RagChunk("margin", "source", "gross margin expanded because AI server mix improved", {}, [0.1, 0.9]),
        rag_runtime.RagChunk("eps", "source", "EPS revision and monthly revenue acceleration", {}, [0.1, 0.8]),
        rag_runtime.RagChunk("cash", "source", "free cash flow conversion", {}, [0.1, 0.7]),
    ])
    index = rag_runtime.InMemoryRagIndex(chunks)

    class PreferKeywordReranker(rag_documents.Reranker):
        async def rerank(self, query, results, top_k=5):
            reranked = sorted(
                results,
                key=lambda item: ("gross margin" in item.chunk.text, item.score),
                reverse=True,
            )
            return reranked[:top_k]

    results = asyncio.run(
        rag_documents.hybrid_search_async(
            index,
            "gross margin EPS monthly revenue",
            query_embedding=[1.0, 0.0],
            candidate_k=20,
            top_k=5,
            reranker=PreferKeywordReranker(),
        )
    )

    assert len(results) == 5
    assert results[0].chunk.chunk_id == "margin"
    assert "hybrid_scores" in results[0].chunk.metadata


def test_ensure_agent_rag_context_records_warnings(monkeypatch):
    index = rag_runtime.InMemoryRagIndex(
        [rag_runtime.RagChunk("x", "source", "downgrade warning " * 40, {})],
        metadata={"warnings": ["document warning"]},
    )
    context = {"data": {"ticker": "AAPL"}, "rag_index": index}

    formatted = rag_runtime.ensure_agent_rag_context(6, context, None)

    assert "RAG 語意檢索精選資料" in formatted
    assert context["rag_status"]["warnings"] == ["document warning"]
