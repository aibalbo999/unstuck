import asyncio
from copy import deepcopy

import pytest

from structured_output_runtime import process_agent_response


COMPLETE = """### Round 1：基本面與護城河
🐂 多頭：依 data.company_summary，業務具有客戶認證門檻；強度仍待驗證。
🐻 空頭：回應認證優勢，競爭者可能追趕；缺少市占證據，不能宣稱獨占。
### Round 2：財務與估值
🐻 空頭：依 data.financial_statements，現金流品質尚待同期間查核。
🐂 多頭：回應現金流風險，成長可能改善效率，但缺資料，不能推定估值折讓。
### Round 3：近期催化劑
🐂 多頭：依 data.recent_catalysts，事件仍需確認實際貢獻。
🐻 空頭：回應事件利多，尚無訂單與營收的因果證據。
**主持人總結：** 正反論點仍有不確定性，不能增加新的價格或結論。
**未解爭點：** 估值與成長假設的期間仍待驗證；應取得同期間來源後重評。
"""


def test_complete_debate_and_missing_round_or_summary_are_distinguished():
    from debate_output_completion import debate_output_issues
    assert debate_output_issues(COMPLETE) == []
    assert debate_output_issues(COMPLETE.split('### Round 3')[0])
    assert debate_output_issues(COMPLETE.split('**主持人總結')[0])
    assert debate_output_issues(COMPLETE.replace('🐻 空頭：', '旁白：', 1))
    assert debate_output_issues(COMPLETE.replace('**未解爭點：**', '**附註：**'))
    assert debate_output_issues(COMPLETE.replace('依 data.company_summary，業務具有客戶認證門檻；強度仍待驗證。', ''))
    assert debate_output_issues(COMPLETE.replace('正反論點仍有不確定性，不能增加新的價格或結論。', ''))


def test_agent6_policy_allows_complete_bounded_debate_without_long_fallback_instruction():
    from agent_runtime.generation_config import (
        build_generation_config, apply_model_generation_policy,
        google_safe_agent_system_instruction, generation_event_metadata,
    )
    for model in ('gemini-3-flash-preview', 'gemini-3.6-flash'):
        prompt = google_safe_agent_system_instruction(6, model)
        config = apply_model_generation_policy(build_generation_config(6, prompt), model, 6)
        assert config.max_output_tokens == 8192
        assert config.thinking_config.thinking_level.lower() == 'low'
        assert 'sufficiently long' not in prompt
        assert '未解爭點' in prompt and '不重貼' in prompt
        assert generation_event_metadata(6, model)['completion_policy_version']


def test_final_repair_cannot_adopt_debate_missing_required_sections():
    from agent_runtime.repair_state import repair_contract_issues
    context = _context()
    context['analyses'][6] = COMPLETE.split('### Round 3')[0]
    assert repair_contract_issues(6, context)
    context['analyses'][6] = COMPLETE
    assert not repair_contract_issues(6, context)


def _context():
    return {'pipeline_id': 'v1', 'data': {'ticker': 'TEST'}, 'analyses': {1: 'prior evidence'},
            'structured_outputs': {}, 'agent_sequence': [1, 6], 'blocking_issues': []}


def _runtime(monkeypatch, finishes):
    from agent_runtime import quality_gates as q, quality_retry
    calls = []
    async def noop(*args, **kwargs): pass
    async def generate(agent, data, context, rotator):
        calls.append(agent)
        reason = finishes[min(len(calls) - 1, len(finishes) - 1)]
        if isinstance(reason, Exception):
            raise reason
        return process_agent_response(agent, COMPLETE if reason == 'STOP' else '未完成', context,
            completion_diagnostics={'finish_reasons': [reason], 'stream_completed': True})
    monkeypatch.setattr(q, 'run_single_agent_async', generate)
    monkeypatch.setattr(q, 'ensure_agent_rag_context_async', noop)
    monkeypatch.setattr(q, 'ensure_context_digest_async', noop)
    monkeypatch.setattr(q, 'get_runtime_model_sequence', lambda *_: ['offline-model'])
    monkeypatch.setattr(quality_retry, 'get_runtime_model_sequence', lambda *_: ['offline-model'])
    monkeypatch.setattr(q, 'validate_analysis_output', lambda *_: [])
    monkeypatch.setattr(q, 'validate_company_identity', lambda *_: [])
    monkeypatch.setattr(q, 'validate_prompt_leakage', lambda *_: [])
    monkeypatch.setattr(q, 'append_quality_warnings', lambda agent, text, data: text)
    return q, calls


def test_truncation_retries_only_agent6_once_and_preserves_upstream(monkeypatch):
    q, calls = _runtime(monkeypatch, ['MAX_TOKENS', 'STOP'])
    context = _context()
    before = deepcopy(context['analyses'])
    asyncio.run(q.run_agent_with_quality_gates_async(6, context['data'], context, object()))
    assert calls == [6, 6]
    assert context['analyses'][1] == before[1]
    assert not context['blocking_issues']
    from memo_output_completion import incomplete_memo_roles
    assert not incomplete_memo_roles(context)


@pytest.mark.parametrize('finishes, expected', [(['MAX_TOKENS', 'MAX_TOKENS'], 2), (['SAFETY'], 1)])
def test_still_incomplete_or_safety_response_stays_blocked(monkeypatch, finishes, expected):
    from memo_output_completion import incomplete_memo_roles
    q, calls = _runtime(monkeypatch, finishes)
    context = _context()
    asyncio.run(q.run_agent_with_quality_gates_async(6, context['data'], context, object()))
    assert len(calls) == expected
    assert incomplete_memo_roles(context)
    assert context['blocking_issues']


def test_recovery_slot_is_saved_before_call_and_cannot_reopen_after_restart(monkeypatch, tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from workflow_quality_drafts import checkpoint_draft_scope, quality_draft_node
    from memo_output_completion import incomplete_memo_roles
    q, calls = _runtime(monkeypatch, ['MAX_TOKENS', RuntimeError('process interruption')])
    path = str(tmp_path / 'debate.sqlite3')
    async def run():
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            await saver.setup()
            context = _context()
            with checkpoint_draft_scope(saver, 'same-job'):
                async with quality_draft_node(6, {'input': 'frozen'}, context):
                    await q.run_agent_with_quality_gates_async(6, context['data'], context, object())
    with pytest.raises(RuntimeError, match='process interruption'):
        asyncio.run(run())
    async def resume():
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            context = _context()
            with checkpoint_draft_scope(saver, 'same-job'):
                async with quality_draft_node(6, {'input': 'frozen'}, context):
                    await q.run_agent_with_quality_gates_async(6, context['data'], context, object())
            assert context['agent_quality_retry_counts'][6] == 1
            assert incomplete_memo_roles(context) and context['blocking_issues']
    asyncio.run(resume())
    assert calls == [6, 6]


def test_spent_quality_retry_does_not_open_another_completion_retry(monkeypatch):
    q, calls = _runtime(monkeypatch, ['MAX_TOKENS', 'STOP'])
    context = _context()
    context['agent_quality_retry_counts'] = {6: 1}
    asyncio.run(q.run_agent_with_quality_gates_async(6, context['data'], context, object()))
    assert calls == [6]
    assert context['blocking_issues']


def test_identity_repair_shares_the_completion_retry_limit(monkeypatch):
    q, calls = _runtime(monkeypatch, ['MAX_TOKENS', 'STOP'])
    monkeypatch.setattr(q, 'validate_company_identity', lambda *_: ['wrong issuer'])
    context = _context()
    asyncio.run(q.run_agent_with_quality_gates_async(6, context['data'], context, object()))
    assert calls == [6, 6]
    assert any('身分' in issue for issue in context['blocking_issues'])


def test_recovery_provider_not_called_if_reservation_checkpoint_fails(monkeypatch, tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    import workflow_quality_drafts as drafts
    import pytest
    q, calls = _runtime(monkeypatch, ['MAX_TOKENS', 'STOP'])
    original = drafts._save_record
    async def save(node, record, **kwargs):
        if record.get('agent_quality_retry_count') == 1:
            raise OSError('checkpoint unavailable')
        await original(node, record, **kwargs)
    monkeypatch.setattr(drafts, '_save_record', save)
    async def run():
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'reservation.sqlite3')) as saver:
            await saver.setup()
            context = _context()
            with drafts.checkpoint_draft_scope(saver, 'reserve-job'):
                async with drafts.quality_draft_node(6, {'input': 'frozen'}, context):
                    await q.run_agent_with_quality_gates_async(6, context['data'], context, object())
    with pytest.raises(OSError, match='checkpoint unavailable'):
        asyncio.run(run())
    assert calls == [6]


def test_identity_allowance_is_persisted_before_call_and_survives_restart(monkeypatch, tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    import workflow_quality_drafts as drafts
    import pytest
    q, calls = _runtime(monkeypatch, ['STOP', RuntimeError('provider interrupted')])
    monkeypatch.setattr(q, 'validate_company_identity', lambda *_: ['wrong company'])
    path = str(tmp_path / 'identity.sqlite3')
    async def run():
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            await saver.setup()
            context = _context()
            with drafts.checkpoint_draft_scope(saver, 'identity-job'):
                async with drafts.quality_draft_node(6, {'input': 'frozen'}, context):
                    await q.run_agent_with_quality_gates_async(6, context['data'], context, object())
            return context
    with pytest.raises(RuntimeError, match='provider interrupted'):
        asyncio.run(run())
    context = asyncio.run(run())
    assert calls == [6, 6]
    assert context['agent_quality_retry_counts'][6] == 1
    assert context['blocking_issues']
