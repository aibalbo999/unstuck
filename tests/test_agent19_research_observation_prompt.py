"""Exercise Agent 19's delivered decision instructions, including fallback models."""

import pytest


def _delivered_prompt(model):
    from agent_runtime.generation_config import google_safe_agent_system_instruction
    from agent_runtime.prompting import build_prompt

    data = {
        "ticker": "6488.TWO",
        "company_name": "環球晶",
        "current_price": 948.0,
        "data_trust": {"status": "fresh", "critical_failures": []},
    }
    state = {"pipeline_id": "v3", "_prompt_model_id": model, "analyses": {}}
    return google_safe_agent_system_instruction(19, model) + build_prompt(19, data, state)


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemma-4-31b-it"])
def test_observation_label_follows_the_decision_without_hiding_missing_valuation(model):
    delivered = _delivered_prompt(model)

    assert "中性觀察／未評估是論點狀態，不等於持有" in delivered
    assert "缺少目標價或僅不宜放空，不強迫改成避免" in delivered
    assert "只有決策確實是不新增部位、等待重新評估時，才以避免表達此觀察政策" in delivered
    assert "持有仍須既有的 12 個月方向依據" in delivered
    assert "不能補價格或只為通過檢查改標籤" in delivered

    # Missing prices must remain disclosed under the existing directional gate.
    assert "N/A／未評估並說明原因，不為補齊期限新增價格" in delivered
    assert "BUY/HOLD/SHORT 分類仍須滿足既有對應的 12 個月報酬與一致性門檻" in delivered
    assert "資料不足不能冒稱通過" in delivered


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemma-4-31b-it"])
def test_genuine_no_position_decision_is_explicit_across_body_and_short_setup(model):
    delivered = _delivered_prompt(model)

    assert "recommendation、analysis_markdown、short_setup.entry_trigger 與 cover_stop 必須一致" in delivered
    assert "entry_trigger 明示目前不建立空方部位並列重評條件" in delivered
    assert "cover_stop 明示「不適用，目前不建立空方部位。」" in delivered
    assert "保留 squeeze_risk 與 thesis_invalidation" in delivered
    assert "不把未知既有持倉寫成續抱、回補或部位退出指令" in delivered

    # The observation wording does not loosen an actual short trade's contract.
    assert "target < entry < stop" in delivered
    assert "借券／成本／催化日期限制完全保留" in delivered
    assert "不得一面指示立即放空一面豁免價位" in delivered
