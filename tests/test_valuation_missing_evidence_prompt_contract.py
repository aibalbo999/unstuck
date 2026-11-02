import json
from pathlib import Path


def test_valuation_missing_scope_does_not_force_rankings_or_classification():
    data=json.loads((Path(__file__).resolve().parents[1]/"backend/prompts/agents.json").read_text())
    system=data["system_prompts"]["4"]
    task=data["analysis_prompts"]["4"]
    assert "同樣紀律適用dcf_reasoning、peer_reasoning、scenario_reasoning與正文" in system
    assert "後附限制不能抵銷" in system
    assert "不為滿足家數" in task
    assert "否則明示【未評估】" in task
    assert "列舉 3-5 個可比公司的估值現狀" not in task
    assert "禁止提出最終買入/賣出/持有建議" in system

    
def test_growth_source_contract_keeps_headlines_and_product_mix_from_proving_moat():
    data=json.loads((Path(__file__).resolve().parents[1]/"backend/prompts/agents.json").read_text())
    system=data["system_prompts"]["5"]
    assert "不證實訂單已拿下" in system
    assert "公司歷史實現營收不等於SOM" in system
    assert "不得覆蓋Agent3已標未評估" in system
    assert "後文限制不能抵銷前文" in system

    
def test_redteam_missing_evidence_is_not_proof_of_distress():
    data=json.loads((Path(__file__).resolve().parents[1]/"backend/prompts/agents.json").read_text())
    system=data["system_prompts"]["21"]
    assert "不等於必須證明公司已受損" in system
    assert "不得套用供應商latest_fcf_conversion" in system
    assert "可少列風險" in system
    assert "不是已測得的違約或跌價機率" in system
