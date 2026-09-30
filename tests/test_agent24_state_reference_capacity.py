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
