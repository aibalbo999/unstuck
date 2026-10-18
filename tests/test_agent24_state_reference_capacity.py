"""Agent 24 can share exact State evidence with its visible financial source."""

import copy
import pytest

from agent_runtime import prompting
from agent_runtime.generation_config import estimate_agent_input_tokens
from state_memory import initialize_agent_state
from test_gemma_state_references import expand_references, financial_payload, state_payload


MODEL = "gemini-3.6-flash"


def _context():
    records = [
        {"date": f"2026-09-{day:02d}", "net_buy": -4321, "missing": None,
         "zero": 0, "flag": False, "warning": "來源限制與反證不得遺失。" * 12}
        for day in range(1, 21)
    ]
    data = {
        "ticker": "TEST.TW", "company_name": "測試公司",
        "chip_data": {"as_of": "2026-09-20", "records": records},
        "data_trust": {"status": "partial"},
    }
    return data, {"_prompt_model_id": MODEL, "pipeline_id": "v4",
                  "agent_state": initialize_agent_state(data), "data": data}


def test_agent24_flash_shares_only_exact_visible_state_evidence(monkeypatch):
    data, context = _context()
    original = copy.deepcopy(data)
    with monkeypatch.context() as patch:
        patch.setattr(prompting, "compact_state_reference_section", lambda financial, state: state)
        before = prompting.build_prompt(24, data, context)
    after = prompting.build_prompt(24, data, context)

    assert "$prompt_ref" in after
    assert financial_payload(after) == financial_payload(before)
    assert expand_references(state_payload(after), financial_payload(after)) == state_payload(before)
    assert before.split("【trade-source:", 1)[1] == after.split("【trade-source:", 1)[1]
    assert estimate_agent_input_tokens(24, MODEL, after) < estimate_agent_input_tokens(24, MODEL, before) - 1000
    assert data == original


@pytest.mark.parametrize("flag", [
    "_audit_retry_instruction", "_audit_reflection_instruction", "_identity_retry_instruction",
])
def test_agent24_repair_keeps_full_guidance_and_exact_state(flag, monkeypatch):
    data, context = _context()
    context[flag] = "核對完整來源與反證。"
    context["_model_sequence_override"] = {24: [MODEL]}
    with monkeypatch.context() as patch:
        patch.setattr(prompting, "compact_state_reference_section", lambda financial, state: state)
        before = prompting.build_prompt(24, data, context)
    after = prompting.build_prompt(24, data, context)

    assert "$prompt_ref" in after
    assert financial_payload(after) == financial_payload(before)
    assert expand_references(state_payload(after), financial_payload(after)) == state_payload(before)
    assert before.split("【trade-source:", 1)[1] == after.split("【trade-source:", 1)[1]
    assert "核對完整來源與反證。" in after
    assert estimate_agent_input_tokens(24, MODEL, after) < estimate_agent_input_tokens(24, MODEL, before) - 1000


def test_agent24_lite_fallback_packs_records_without_losing_evidence(monkeypatch):
    from test_gemma_state_references import financial_payload, state_payload, expand_references

    data, context = _context()
    context['_prompt_model_id'] = 'gemini-3.5-flash-lite'
    original = copy.deepcopy((data, context))
    formatter = prompting.format_data_for_prompt

    def unpacked_format(value, **kwargs):
        if value.get('_prompt_agent_num') == 24:
            kwargs.pop('dense', None)
            kwargs['compact_json'] = True
        return formatter(value, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(prompting, 'format_data_for_prompt', unpacked_format)
        before = prompting.build_prompt(24, data, context)
    after = prompting.build_prompt(24, data, context)

    assert '__record_table__' in after
    assert financial_payload(after) == financial_payload(before)
    assert expand_references(state_payload(after), financial_payload(after)) == (
        expand_references(state_payload(before), financial_payload(before))
    )
    assert before.split('【trade-source:', 1)[1] == after.split('【trade-source:', 1)[1]
    assert estimate_agent_input_tokens(24, context['_prompt_model_id'], after) < (
        estimate_agent_input_tokens(24, context['_prompt_model_id'], before) - 100
    )
    assert data == original[0]
    assert context['agent_state'] == original[1]['agent_state']
