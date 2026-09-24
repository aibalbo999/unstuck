"""Agent19 input admission uses lossless JSON formatting, never less evidence."""
import copy
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from agent_runtime import prompting
from agent_runtime.generation_config import estimate_agent_input_tokens
from agent_runtime.single_agent_admission import _preflight_model_input_capacity
from fixtures.data_payloads import fresh_audited_payload
from prompt_builder import format_data_for_prompt
from llm_input_capacity import InputCapacityExceededError
from workflow_context import legacy_context_from_graph


MODEL = 'gemini-3.5-flash-lite'
STRING_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"')


def financial_json(section):
    return section.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0]


def assert_lossless(original, compact):
    before, after = financial_json(original), financial_json(compact)
    assert json.dumps(json.loads(before), ensure_ascii=False, sort_keys=True) == json.dumps(
        json.loads(after), ensure_ascii=False, sort_keys=True)
    # Includes escaped quotes, internal spaces, tabs/newlines, every key and quote.
    assert STRING_TOKEN.findall(before) == STRING_TOKEN.findall(after)
    assert original.split('【使用規則】', 1)[1] == compact.split('【使用規則】', 1)[1]


def test_compact_json_preserves_values_order_string_bytes_and_rules_without_table_refs():
    data = fresh_audited_payload()
    data['institutional_trading']['verbatim'] = '  原文 "quote"  x\ty\nz\\w  '
    data['institutional_trading']['values'] = [None, False, True, 0, -1, 1.5, ' 0 ']
    data['source_freshness']['padding'] = 'preserve ' * 80
    data['data_freshness'] = {'source_freshness': copy.deepcopy(data['source_freshness'])}
    before = copy.deepcopy(data)
    original = format_data_for_prompt(data)
    compact = format_data_for_prompt(data, compact_json=True)
    assert_lossless(original, compact)
    assert len(compact) < len(original)
    assert '__record_table__' not in compact and '"$ref"' not in compact
    assert data == before


@pytest.mark.parametrize('agent,model,repair', [
    (19, MODEL, False), (19, MODEL, True),
    (19, 'gemini-3.8-flash', False), (19, 'gemma-4-31b-it', False),
    (18, MODEL, False), (7, MODEL, False), (24, MODEL, False),
])
def test_non_gemma_agents_use_lossless_financial_representation(monkeypatch, agent, model, repair):
    data = fresh_audited_payload()
    context = {'data': data, 'ticker': data['ticker'], 'company_name': data['company_name'],
               'pipeline_id': 'v3', '_prompt_model_id': model, 'analyses': {}, 'structured_outputs': {}}
    if repair:
        context['_audit_retry_instruction'] = '保留完整來源，重新驗證。'
    captures = []
    def formatter(data, **kwargs):
        result = format_data_for_prompt(data, **kwargs)
        captures.append((copy.deepcopy(data), kwargs, result))
        return result
    monkeypatch.setattr(prompting, 'format_data_for_prompt', formatter)
    prompt = prompting.build_prompt(agent, data, context)
    routed, options, result = captures[0]
    if model != 'gemma-4-31b-it':
        assert options.get('compact_json') is True
        assert_lossless(format_data_for_prompt(routed, compact=options.get('compact', False)), result)
    else:
        assert not options.get('compact_json')
    assert prompt.count(result) == 1


@pytest.mark.skipif(not os.getenv('AGENT19_CAPACITY_CHECKPOINT'), reason='optional private canary checkpoint')
def test_original_canary_checkpoint_fits_unchanged_64k_with_all_evidence(monkeypatch):
    state = json.loads(Path(os.environ['AGENT19_CAPACITY_CHECKPOINT']).read_text())
    context = legacy_context_from_graph(state, SimpleNamespace(progress_callback=None, cancel_check=None))
    context['_prompt_model_id'] = MODEL
    before = copy.deepcopy(context['data'])
    normal_formatter = prompting.format_data_for_prompt
    def legacy_format(data, **kwargs):
        kwargs.pop('compact_json', None)
        return normal_formatter(data, **kwargs)
    monkeypatch.setattr(prompting, 'format_data_for_prompt', legacy_format)
    legacy = prompting.build_prompt(19, context['data'], context)
    monkeypatch.setattr(prompting, 'format_data_for_prompt', normal_formatter)
    optimized = prompting.build_prompt(19, context['data'], context)
    assert estimate_agent_input_tokens(19, MODEL, legacy) > 64000
    assert estimate_agent_input_tokens(19, MODEL, optimized) < 64000
    # The isolated runner does not load the formal .env; bind the observed
    # admission limit explicitly without changing production configuration.
    from agent_runtime import single_agent_admission
    monkeypatch.setattr(single_agent_admission.config, 'MODEL_INPUT_TOKEN_LIMITS', {MODEL: 64000})
    monkeypatch.setattr(single_agent_admission.config, 'TPM_LIMITS', {})
    with pytest.raises(InputCapacityExceededError) as rejected:
        _preflight_model_input_capacity(19, MODEL, legacy)
    assert rejected.value.limit == 64000
    assert rejected.value.basis == 'local_input_budget'
    assert_lossless(legacy, optimized)
    # Removing just the financial JSON must leave every other character intact.
    assert legacy.replace(financial_json(legacy), '', 1) == optimized.replace(financial_json(optimized), '', 1)
    _preflight_model_input_capacity(19, MODEL, optimized)
    assert context['data'] == before
