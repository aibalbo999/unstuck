import json
import pytest
from agent_runtime import generation_config as generation
from structured_output_runtime import process_agent_response
from agent_runtime.quality_structured_outputs import try_parse_structured_output


@pytest.mark.parametrize("model",["gemini-3.6-flash","gemini-3.8-flash","gemini-3-flash-preview"])
def test_moat_budget_preserves_schema_sampling_and_low_thinking(model):
    config=generation.build_generation_config(3,"same system")
    before=config.model_dump()
    adjusted=generation.apply_model_generation_policy(config,model,3)
    assert adjusted.max_output_tokens==8192
    assert adjusted.temperature==.30 and adjusted.top_p==.90
    assert adjusted.response_schema==config.response_schema
    assert config.model_dump()==before
    assert adjusted.thinking_config.thinking_level.value=="LOW"
    assert generation.generation_profile(1)["max_output_tokens"]==8192
    assert generation.generation_profile(2)["max_output_tokens"]==8192
    assert generation.generation_profile(6)["max_output_tokens"]==8192
    assert generation.generation_profile(20)["max_output_tokens"]==1024


def test_more_output_room_never_certifies_provider_truncation():
    from moat_assessment import MOAT_FIELDS
    raw=json.dumps({"reasoning_steps":["來源","反證","限制"],"moat_scores":dict.fromkeys(MOAT_FIELDS),
        "analysis_markdown":"缺乏來源，評分未評估。"},ensure_ascii=False)
    context={"pipeline_id":"v1","data":{}}
    text=process_agent_response(3,raw,context,completion_diagnostics={"finish_reasons":["MAX_TOKENS"]})
    assert context["structured_outputs"][3]["output_completion"]["status"]=="incomplete"
    assert not try_parse_structured_output(3,text,context)[0]


def test_moat_system_and_user_contract_do_not_force_missing_evidence_rankings():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    prompts=json.loads((root/"backend/prompts/agents.json").read_text())
    role3=[section["3"] for section in prompts.values() if isinstance(section,dict) and isinstance(section.get("3"),str)]
    assert len(role3)==2
    for text in role3:
        assert "口徑" in text and "未評估" in text and "reasoning_steps" in text
        assert "最弱" in text and ("不得排序" in text or "無法排序" in text)
        assert "必須直接引用" not in text
    # The repair must remain role scoped and keep score 1 distinct from null.
    assert any("1-3：護城河很弱或不存在" in text for text in role3)
