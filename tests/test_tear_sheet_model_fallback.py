"""A rejected or quota-limited summary can use existing routes with the same gates."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
import pytest

@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('first_failure', ['429', '504', 'quality'])
def test_summary_uses_configured_backup_without_accepting_failed_prose(monkeypatch, asynchronous, first_failure):
    import tear_sheet_tasks as summary
    import agent_runtime.llm_waiting as waiting
    class Rotator:
        keys = ['fixture']
    monkeypatch.setattr(summary, 'KeyRotator', Rotator)
    monkeypatch.setattr(summary, '_tear_sheet_model_sequence', lambda: ['gemini-primary', 'gemini-backup'])
    monkeypatch.setattr(waiting, 'acquire_key', lambda *a, **k: 'fixture')
    async def acquire(*a, **k):return 'fixture'
    monkeypatch.setattr(waiting, 'acquire_key_async', acquire)
    calls = []
    class ProviderError(RuntimeError):
        code = int(first_failure) if first_failure != 'quality' else 429
    def generate(key, model, prompt):
        calls.append(model)
        if model == 'gemini-primary' and first_failure != 'quality':raise ProviderError('private-error')
        text = '研究分類：買入。' if model == 'gemini-primary' else '研究分類：避免。尚缺合格估值假設，目標價未提供。'
        return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason='STOP')], usage_metadata=None)
    async def agenerate(*a):return generate(*a)
    monkeypatch.setattr(summary, '_generate_tear_sheet_content', generate)
    monkeypatch.setattr(summary, '_generate_tear_sheet_content_async', agenerate)
    context = {'pipeline_id':'v1','data':{},'parsed':{'recommendation':{'建議':'避免'}}}
    before = deepcopy(context['parsed'])
    if asynchronous:asyncio.run(summary.ensure_tear_sheet_summary_async(context, Rotator()))
    else:summary.ensure_tear_sheet_summary(context, Rotator())
    assert calls == ['gemini-primary','gemini-backup']
    assert context['tear_sheet_validation']['status'] == 'accepted'
    assert context['tear_sheet_summary'].startswith('研究分類：避免。')
    assert context['parsed'] == before


def test_summary_backups_are_existing_google_routes_deduplicated(monkeypatch):
    import tear_sheet_tasks as summary
    import agent_runtime.routing as routing
    monkeypatch.setattr(summary, 'TEAR_SHEET_MODEL', 'gemini-primary')
    monkeypatch.setattr(routing, 'get_audit_model_sequence', lambda: ['gemini-primary','gemini-backup','openai:other'])
    assert summary._tear_sheet_model_sequence() == ['gemini-primary','gemini-backup']


def test_tear_sheet_prompt_excludes_private_receipt_paths_without_mutating_evidence():
    from copy import deepcopy
    from tear_sheet_tasks import _build_tear_sheet_prompt
    context={"data":{"ticker":"1623.TW","institutional_trading":{"total_net_shares":123,"raw_evidence":{"source_url":"https://www.twse.com.tw/official","raw_response_sha256":"a"*64,"raw_response_path":"/Volumes/X10 Pro Mac/stock-agent/backend/cache/official-response-evidence/private.gz"}}},"analyses":{},"parsed":{}}
    original=deepcopy(context)
    prompt=_build_tear_sheet_prompt(context)
    assert "raw_response_path" not in prompt
    assert "/Volumes/X10 Pro Mac/" not in prompt
    assert "https://www.twse.com.tw/official" in prompt
    assert '"total_net_shares": 123' in prompt
    assert context==original
