"""Mode-D fallback capacity retains every financial source, quote and source card."""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_runtime import prompting
from agent_runtime.generation_config import estimate_agent_input_tokens
from agent_runtime.single_agent_prompt import build_model_prompt
from agent_runtime.step_cache import build_agent_step_cache_key
from fixtures.data_payloads import fresh_audited_payload
from test_agent19_lossless_prompt_json import assert_lossless, financial_json, STRING_TOKEN
from workflow_context import legacy_context_from_graph

MODEL = 'gemini-3.5-flash-lite'


def compare_prompts(monkeypatch, ctx, model=MODEL):
    formatter = prompting.format_data_for_prompt
    def legacy(data, **kwargs):
        kwargs['compact_json'] = False
        return formatter(data, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(prompting, 'format_data_for_prompt', legacy)
        before = build_model_prompt(24, ctx['data'], ctx, model, False, prompt_builder=prompting.build_prompt)
    after = build_model_prompt(24, ctx['data'], ctx, model, False, prompt_builder=prompting.build_prompt)
    return before, after


@pytest.mark.parametrize('repair', [False, True])
@pytest.mark.parametrize('model', [MODEL, 'gemini-3.8-flash'])
def test_initial_and_repair_use_lossless_compact_without_removing_source_cards(monkeypatch, repair, model):
    data = fresh_audited_payload()
    data['institutional_trading']['verbatim'] = '  quoted "原文"  x\ty\nz\\w '
    ctx = {'data': data, 'ticker': data['ticker'], 'company_name': data['company_name'],
           'pipeline_id': 'v4', 'analyses': {22: '保持技術原文', 23: '保持籌碼原文'}, 'structured_outputs': {},
           'rag_context': {24: '保持RAG逐字來源'}}
    if repair:
        ctx['_audit_retry_instruction'] = '保留所有引用重新核驗。'
    original = copy.deepcopy(data)
    before, after = compare_prompts(monkeypatch, ctx, model)
    assert len(after) < len(before)
    assert_lossless(before, after)
    assert before.replace(financial_json(before), '', 1) == after.replace(financial_json(after), '', 1)
    assert '【同一來源的有限事實句示例' in after
    assert '保持RAG逐字來源' in after and '保持技術原文' in after
    assert build_agent_step_cache_key(24, data, ctx, model, before) != build_agent_step_cache_key(24, data, ctx, model, after)
    assert data == original


def test_gemma_mode_d_keeps_existing_dense_representation(monkeypatch):
    data = fresh_audited_payload()
    ctx = {'data': data, 'ticker': data['ticker'], 'company_name': data['company_name'],
           'pipeline_id': 'v4', 'analyses': {}, 'structured_outputs': {}}
    captures = []
    formatter = prompting.format_data_for_prompt
    def capture(value, **kwargs):
        captures.append(kwargs.copy())
        return formatter(value, **kwargs)
    monkeypatch.setattr(prompting, 'format_data_for_prompt', capture)
    build_model_prompt(24, data, ctx, 'gemma-4-31b-it', False, prompt_builder=prompting.build_prompt)
    assert captures[0].get('dense') is True
    assert not captures[0].get('compact_json')


@pytest.mark.skipif(not os.getenv('AGENT24_CAPACITY_CHECKPOINT'), reason='optional private canary checkpoint')
def test_actual_3037_checkpoint_fits_without_changing_input_or_source_catalog(monkeypatch):
    state = json.loads(Path(os.environ['AGENT24_CAPACITY_CHECKPOINT']).read_text())
    ctx = legacy_context_from_graph(state, SimpleNamespace(progress_callback=None, cancel_check=None))
    original = copy.deepcopy(ctx['data'])
    before, after = compare_prompts(monkeypatch, ctx)
    old_tokens = estimate_agent_input_tokens(24, MODEL, before)
    new_tokens = estimate_agent_input_tokens(24, MODEL, after)
    assert old_tokens > 64000
    assert new_tokens < 64000
    # 1,253 tokens were not checkpointed (Agent24 RAG/prompt-local state).
    # Preserve this measured live-vs-checkpoint gap rather than claim exact reconstruction.
    assert new_tokens + max(0, 66577 - old_tokens) < 64000
    assert_lossless(before, after)
    assert before.replace(financial_json(before), '', 1) == after.replace(financial_json(after), '', 1)
    assert ctx['data'] == original
    assert '【trade-source:' in after and '【同一來源的有限事實句示例' in after
