import asyncio
from types import SimpleNamespace

import pytest

from rag_runtime import embeddings
from rag_runtime.types import RagChunk


@pytest.mark.parametrize('async_mode', [False, True])
def test_embedding_batches_preserve_order_cache_and_budget(monkeypatch, async_mode):
    calls = []
    cache = {'cached': [99.0]}
    monkeypatch.setattr(embeddings, 'TPM_LIMITS', {embeddings.EMBEDDING_MODEL: 10})
    monkeypatch.setattr(embeddings, 'MODEL_INPUT_TOKEN_LIMITS', {})
    monkeypatch.setattr(embeddings, 'estimate_input_tokens', lambda text: len(text))
    monkeypatch.setattr(embeddings, '_get_cached_embedding', lambda model, text, *args: cache.get(text))
    monkeypatch.setattr(embeddings, '_set_cached_embedding', lambda model, text, config, vector, *args: cache.update({text: vector}))

    class Rotator:
        def get_key(self, model, estimated_tokens):
            assert 0 < estimated_tokens <= 10
            return 'test-key'
        async def async_get_key(self, *args):
            return self.get_key(*args)
    monkeypatch.setattr(embeddings, 'KeyRotator', Rotator)

    def embed(key, model, texts, config):
        calls.append(texts)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[float(ord(text[0]))]) for text in texts])
    async def embed_async(*args):
        return embed(*args)
    monkeypatch.setattr(embeddings, 'embed_content', embed)
    monkeypatch.setattr(embeddings, 'embed_content_async', embed_async)
    chunks = [RagChunk(str(i), 'source', text, {}) for i, text in enumerate(['aaaaaa', 'cached', 'bbbbbb', 'cc'])]
    warnings = asyncio.run(embeddings.embed_index_chunks_async(chunks, {}, Rotator())) if async_mode else embeddings.embed_index_chunks(chunks, {}, Rotator())
    assert warnings == []
    assert len(calls) == 2
    assert [chunk.embedding for chunk in chunks] == [[97.0], [99.0], [98.0], [99.0]]
    calls.clear()
    warnings = asyncio.run(embeddings.embed_index_chunks_async(chunks, {}, Rotator())) if async_mode else embeddings.embed_index_chunks(chunks, {}, Rotator())
    assert not calls


def test_single_oversized_embedding_is_not_silently_truncated(monkeypatch):
    from llm_input_capacity import InputCapacityExceededError
    monkeypatch.setattr(embeddings, 'TPM_LIMITS', {embeddings.EMBEDDING_MODEL: 10})
    monkeypatch.setattr(embeddings, 'MODEL_INPUT_TOKEN_LIMITS', {})
    monkeypatch.setattr(embeddings, 'estimate_input_tokens', len)
    with pytest.raises(InputCapacityExceededError):
        list(embeddings._embedding_batches(['x' * 11]))


@pytest.mark.parametrize('async_mode', [False, True])
@pytest.mark.parametrize('budget_block', [False, True])
def test_later_batch_failure_preserves_cached_and_successful_vectors(monkeypatch, async_mode, budget_block):
    from llm_daily_budget import DailyBudgetBlockedError
    monkeypatch.setattr(embeddings, 'TPM_LIMITS', {embeddings.EMBEDDING_MODEL: 10})
    monkeypatch.setattr(embeddings, 'MODEL_INPUT_TOKEN_LIMITS', {})
    monkeypatch.setattr(embeddings, 'estimate_input_tokens', len)
    monkeypatch.setattr(embeddings, '_get_cached_embedding', lambda model, text, *args: [99.0] if text == 'cached' else None)
    monkeypatch.setattr(embeddings, '_set_cached_embedding', lambda *args: None)

    class Rotator:
        calls = 0
        def get_key(self, *args):
            self.calls += 1
            if budget_block and self.calls == 2:
                raise DailyBudgetBlockedError('embedding', 60, 'daily_budget_exhausted')
            return 'test-key'
        async def async_get_key(self, *args):
            return self.get_key(*args)
        def penalize(self, *args):
            pass
    monkeypatch.setattr(embeddings, 'KeyRotator', Rotator)
    def embed(key, model, texts, config):
        if texts == ['bbbbbb']:
            raise RuntimeError('429 quota')
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[97.0])])
    async def embed_async(*args):
        return embed(*args)
    monkeypatch.setattr(embeddings, 'embed_content', embed)
    monkeypatch.setattr(embeddings, 'embed_content_async', embed_async)
    chunks = [RagChunk(str(i), 'source', text, {}) for i, text in enumerate(['aaaaaa', 'cached', 'bbbbbb'])]
    warnings = asyncio.run(embeddings.embed_index_chunks_async(chunks, {}, Rotator())) if async_mode else embeddings.embed_index_chunks(chunks, {}, Rotator())
    assert warnings
    assert [chunk.embedding for chunk in chunks] == [[97.0], [99.0], None]
