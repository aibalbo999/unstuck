"""Optional LLM helpers must yield to deterministic fallbacks under local load."""
import asyncio
from types import SimpleNamespace
import pytest
import agent_runtime
from llm_key_admission import check_key_admission, key_wait_intervals


@pytest.mark.parametrize('role', ['digest', 'tear_sheet', 'reflection'])
@pytest.mark.parametrize('asynchronous', [False, True])
def test_throttled_auxiliary_never_sends_after_admission_deadline(monkeypatch, role, asynchronous):
    import agent_runtime.llm_waiting as waiting
    import context_digest_tasks as digest
    import tear_sheet_tasks as tear
    import agent_runtime.repair_reflection as reflection
    clock = [0.0]
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr(waiting, 'LLM_KEY_ADMISSION_TIMEOUT_SECONDS', 15.0)
    sent = []

    class Rotator:
        def get_key(self, *args, **kwargs):
            clock[0] += next(key_wait_intervals(60))
            check_key_admission()
            return 'offline-key'
        async def async_get_key(self, *args, **kwargs):
            return self.get_key(*args, **kwargs)

    def generated(*args, **kwargs):
        sent.append(True)
        return SimpleNamespace(text='完整摘要')
    async def generated_async(*args, **kwargs):
        return generated(*args, **kwargs)
    ctx = {'pipeline_id': 'v1', 'data': {'ticker': 'TEST'}, 'analyses': {11: '既有證據'}, 'structured_outputs': {}}
    if role == 'digest':
        monkeypatch.setattr(digest, '_context_digest_model_sequence', lambda: ['aux-model'])
        monkeypatch.setattr(digest, '_get_cached_context_digest', lambda *a: None)
        monkeypatch.setattr(digest, '_store_cached_context_digest', lambda *a: None)
        monkeypatch.setattr(digest, '_is_context_digest_model_circuit_open', lambda *a: False)
        monkeypatch.setattr(digest, '_generate_context_digest_content', generated)
        monkeypatch.setattr(digest, '_generate_context_digest_content_async', generated_async)
        fn = digest.ensure_context_digest_async if asynchronous else digest.ensure_context_digest
        args = (4, ctx, Rotator())
    elif role == 'tear_sheet':
        monkeypatch.setattr(tear, 'KeyRotator', Rotator)
        monkeypatch.setattr(tear, '_tear_sheet_model_sequence', lambda: ['aux-model'])
        monkeypatch.setattr(tear, '_generate_tear_sheet_content', generated)
        monkeypatch.setattr(tear, '_generate_tear_sheet_content_async', generated_async)
        fn = tear.ensure_tear_sheet_summary_async if asynchronous else tear.ensure_tear_sheet_summary
        args = (ctx, Rotator())
    else:
        monkeypatch.setattr(reflection, 'KeyRotator', Rotator)
        monkeypatch.setattr(reflection, 'get_audit_model_sequence', lambda: ['aux-model'])
        monkeypatch.setattr(reflection, '_generate_reflection_content', generated)
        monkeypatch.setattr(reflection, '_generate_reflection_content_async', generated_async)
        fn = reflection.generate_audit_reflection_async if asynchronous else reflection.generate_audit_reflection
        args = (4, ['缺乏計算依據'], '原文', ctx['data'], Rotator())
    result = asyncio.run(fn(*args)) if asynchronous else fn(*args)
    assert sent == []
    assert clock[0] == 15
    if role == 'digest':
        assert 'context_digests' in ctx and ctx['context_digests'][4]
    if role == 'reflection':
        assert '反思摘要' in result
