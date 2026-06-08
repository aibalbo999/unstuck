import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import agent_runtime.audit_repair as audit_repair  # noqa: E402
import agent_runtime.legacy_agent_runner as ar  # noqa: E402
import agent_runtime.repair_circuit_breaker as repair_breaker  # noqa: E402


def base_data():
    return {
        "ticker": "1623.TW",
        "company_name": "大東電 / TA TUN ELECTRIC WIRE CABLE CO L",
        "current_price": 1000.0,
        "fetch_date": "2026年06月01日",
        "price_history": {},
    }


def complete_context():
    data = base_data()
    context = {
        "data": data,
        "analyses": {
            1: "## 商業模式\n大東電以電線電纜為核心業務。",
            2: "## 財務分析\n採用同期間年度資料，若口徑不同僅列資料品質警示。",
            3: "## 護城河\n護城河中等。",
            4: "## 估值\n採用 normalized DCF 與相對估值交叉檢查。",
            5: "## 成長\n成長假設需搭配產能、CapEx、折舊與良率。",
            6: "## 多空辯論\n多空雙方皆引用同一標的資料。",
            7: "## 最終投資決策\n建議持有。",
        },
        "structured_outputs": {
            3: {"moat_scores": {"品牌影響力": 3, "網路效應": 1, "轉換成本": 4, "成本優勢": 3, "專利技術": 3, "整體護城河": 3}},
            4: {"price_targets": {"熊市情境": 800, "基本情境": 1000, "牛市情境": 1200}},
            7: {"recommendation": {"建議": "持有", "短期目標（3個月）": "NT$900", "中期目標（6個月）": "NT$1000", "長期目標（12個月）": "NT$1100", "長期潛力（5年）": "NT$1500", "信心指數": "6/10"}},
        },
    }
    context["parsed"] = ar.parse_structured_data(context)
    return context


def complete_v2_context():
    data = {
        **base_data(),
        "ticker": "2449.TW",
        "company_name": "京元電子 / King Yuan Electronics Co., Ltd.",
        "current_price": 309.5,
    }
    context = {
        "ticker": "2449.TW",
        "company_name": "京元電子 / King Yuan Electronics Co., Ltd.",
        "pipeline_id": "v2",
        "data": data,
        "analyses": {
            11: "## 總經\nAI 與高階測試需求帶來溫和順風。",
            12: "## 商業模式\n京元電子以半導體測試服務收費。",
            13: "## 財務排雷\n財務體質評級：【尚可】。",
            14: "## 成長與估值\nAI/HPC 測試為核心成長來源。",
            15: "## 籌碼\n資金動能評估：【中性】。",
            16: "## 投資決策\n採取持有並等待回檔。",
        },
        "structured_outputs": {
            12: {"moat_scores": {"品牌影響力": 4, "網路效應": 2, "轉換成本": 7, "成本優勢": 6, "專利技術": 7, "整體護城河": 5.2}},
            14: {"price_targets": {"熊市情境": 182, "基本情境": 273, "牛市情境": 379}},
            16: {"recommendation": {"建議": "持有", "短期目標（3個月）": "NT$273", "中期目標（6個月）": "NT$310", "長期目標（12個月）": "NT$350", "長期潛力（5年）": "NT$500", "信心指數": "7/10"}},
        },
    }
    context["parsed"] = ar.parse_structured_data(context)
    return context


def setup_function():
    audit_repair.clear_repair_429_circuit()
    repair_breaker.clear_repair_429_circuit()


def test_structured_repair_falls_back_when_valuation_json_remains_unparseable():
    context = complete_v2_context()
    context["structured_outputs"].pop(14)
    context["analyses"][14] = (
        '{\n  "price_targets": {\n'
        '    "dcf_reasoning": "估值文字存在，但 JSON 在 peer_reasoning 中斷裂。",\n'
        '    "peer_reasoning": "Intel 毛利率 37.2%、營業利益率 6.88%\n'
    )

    ok, message = audit_repair._deterministic_structured_fallback(
        14,
        context["data"],
        context,
        context["analyses"][14],
    )

    assert ok is True
    assert "三情境估值 fallback" in message
    assert set(context["structured_outputs"][14]["price_targets"]) == {"熊市情境", "基本情境", "牛市情境"}
    assert "[目標股價]" in context["analyses"][14]
    assert '"peer_reasoning": "Intel' not in context["analyses"][14]


def test_structured_repair_uses_fallback_when_model_repair_is_429_unavailable():
    context = complete_v2_context()
    context["structured_outputs"].pop(14)
    context["analyses"][14] = "## 二、DCF 模型與情境分析\n模型文字存在，但未提供可解析三情境 JSON。"
    with patch.object(
        audit_repair,
        "run_single_agent",
        return_value="[Agent 14 執行失敗：所有模型/Key 不可用，最後錯誤：429 RESOURCE_EXHAUSTED]",
    ):
        ok, message = audit_repair._repair_agent_output(
            14,
            context["data"],
            context,
            object(),
            ["三情境目標價 未提供可解析 JSON 結構化輸出。"],
        )

    assert ok is True
    assert "模型修復暫不可用" in message
    assert context["deterministic_fallbacks"][0]["trigger"] == "repair_429_failure"
    assert "429" in context["deterministic_fallbacks"][0]["raw_failure"]
    assert set(context["structured_outputs"][14]["price_targets"]) == {"熊市情境", "基本情境", "牛市情境"}


def test_repair_429_circuit_persists_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(repair_breaker.config, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    repair_breaker.clear_repair_429_circuit()

    updated = repair_breaker.record_repair_429_failure(16, "429 RESOURCE_EXHAUSTED")

    assert updated["open"] is True
    state = repair_breaker.repair_429_circuit_state(16)
    assert state["open"] is True
    assert state["failures"] == 1
    assert "429" in state["last_error"]

    repair_breaker.clear_repair_429_circuit(16)
    assert repair_breaker.repair_429_circuit_state(16) == {"open": False, "failures": 0}


def test_repair_429_circuit_expires_after_cooldown(tmp_path, monkeypatch):
    monkeypatch.setattr(repair_breaker.config, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("REPAIR_429_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "10")
    times = iter([100.0, 111.5])
    monkeypatch.setattr(repair_breaker, "_now", lambda: next(times))
    repair_breaker.clear_repair_429_circuit()

    repair_breaker.record_repair_429_failure(16, "too many requests")

    assert repair_breaker.repair_429_circuit_state(16) == {"open": False, "failures": 0}


def test_structured_repair_does_not_fallback_for_non_429_execution_failure():
    context = complete_v2_context()
    context["structured_outputs"].pop(14)
    context["analyses"][14] = "## 二、DCF 模型與情境分析\n模型文字存在，但未提供可解析三情境 JSON。"
    with patch.object(
        audit_repair,
        "run_single_agent",
        return_value="[Agent 14 執行失敗：所有模型/Key 不可用，最後錯誤：503 UNAVAILABLE]",
    ):
        ok, message = audit_repair._repair_agent_output(
            14,
            context["data"],
            context,
            object(),
            ["三情境目標價 未提供可解析 JSON 結構化輸出。"],
        )

    assert ok is False
    assert "503 UNAVAILABLE" in message
    assert 14 not in context["structured_outputs"]
    assert "deterministic_fallbacks" not in context


def test_recommendation_structured_fallback_preserves_report_contract():
    context = complete_v2_context()
    context["structured_outputs"].pop(16)
    context["parsed"] = ar.parse_structured_data(context)

    ok, message = audit_repair._deterministic_structured_fallback(
        16,
        context["data"],
        context,
        "[投資建議]\n建議: 持有\n信心指數: 6/10\n[/投資建議]",
    )

    assert ok is True
    assert "投資建議 fallback" in message
    assert "[投資建議]" in context["analyses"][16]
    assert "建議: 持有" in context["analyses"][16]


def test_financial_quality_repair_uses_safe_fallback_when_model_429_unavailable():
    audit_repair.clear_repair_429_circuit(2)
    repair_breaker.clear_repair_429_circuit(2)
    context = complete_context()
    context["analyses"][2] = (
        "Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率及權益乘數拼接成 TTM 杜邦公式，"
        "2025年營收為72.7B，TTM營收為99.79B，營收年增率高達196.0%。"
    )
    issues = ar.validate_analysis_output(2, context["analyses"][2], context["data"])
    assert issues
    with patch.object(
        audit_repair,
        "run_single_agent",
        return_value="[Agent 2 執行失敗：所有模型/Key 不可用，最後錯誤：429 RESOURCE_EXHAUSTED]",
    ):
        ok, message = audit_repair._repair_agent_output(
            2,
            context["data"],
            context,
            object(),
            issues,
        )

    assert ok is True
    assert "財務品質 fallback" in message
    assert "保守口徑" in context["analyses"][2]
    assert "大東電" in context["analyses"][2]
    assert "京元電子" not in context["analyses"][2]
    assert context["deterministic_fallbacks"][0]["trigger"] == "repair_429_failure"
    assert ar.validate_analysis_output(2, context["analyses"][2], context["data"]) == []
