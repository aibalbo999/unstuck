from agent_runtime.generation_config import google_safe_agent_system_instruction


def test_actual_agent6_system_contract_separates_accounting_amounts_from_capabilities():
    system=google_safe_agent_system_instruction(6,"gemini-3.8-flash")
    assert "公司產品營收或占比不等於市場滲透率" in system
    assert "不直接證明負擔沉重" in system
    assert "Agent4未評估時" in system
    assert "存貨現金影響只是會計組成" in system
    assert "多頭必須用未來成長潛力" not in system
    assert "主持人必須保留每個未核實前提" in system
