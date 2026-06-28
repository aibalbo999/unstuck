import asyncio
import httpx
import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import agent_runtime.legacy_agent_runner as ar  # noqa: E402
import agent_runtime.audit_repair as audit_repair  # noqa: E402
import agent_runtime.repair_reflection as repair_reflection  # noqa: E402
from agent_runtime.deterministic_fallbacks import _deterministic_structured_fallback  # noqa: E402
import assistant_tasks  # noqa: E402
import config  # noqa: E402
import external_data_clients as edc  # noqa: E402
import external_http_client  # noqa: E402
import data_fetch.cache_helpers as cache_helpers  # noqa: E402
import data_fetch.optional_enrichment as optional_enrichment  # noqa: E402
import data_fetch.yfinance_core_fetch as financial_data  # noqa: E402
import financial_tools  # noqa: E402
from confidence_calibration import build_confidence_calibration  # noqa: E402
import prompt_builder  # noqa: E402
import pipeline_modes  # noqa: E402
import rag_runtime  # noqa: E402
import reporting.legacy_report_gen as report_gen  # noqa: E402
import reporting.utils as report_utils  # noqa: E402
import structured_outputs  # noqa: E402
from quant_engine import QuantEngine  # noqa: E402
from llm_client import KeyRotator  # noqa: E402
from openai_structured_outputs import openai_json_schema_response_format  # noqa: E402
from structured_output_models import PriceTargetStructuredOutput  # noqa: E402


def base_data():
    return {
        "ticker": "1623.TW",
        "company_name": "大東電 / TA TUN ELECTRIC WIRE CABLE CO L",
        "current_price": 1000.0,
        "fetch_date": "2026年06月01日",
        "price_history": {},
        "company_identity": {
            "ticker": "1623.TW",
            "stock_id": "1623",
            "official_name": "大東電",
            "allowed_aliases": ["大東電", "1623.TW"],
            "forbidden_aliases": ["大亞", "大亞電線電纜"],
            "same_industry_peers": [{"stock_id": "1609", "stock_name": "大亞"}],
        },
    }


def complete_context():
    data = base_data()
    context = {
        "pipeline_id": "v1",
        "agent_sequence": (1, 2, 3, 4, 5, 6, 7),
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
            3: {
                "moat_scores": {
                    "品牌影響力": 3,
                    "網路效應": 1,
                    "轉換成本": 4,
                    "成本優勢": 3,
                    "專利技術": 3,
                    "整體護城河": 3,
                }
            },
            4: {"price_targets": {"熊市情境": 800, "基本情境": 1000, "牛市情境": 1200}},
            7: {
                "recommendation": {
                    "建議": "持有",
                    "短期目標（3個月）": "NT$900",
                    "中期目標（6個月）": "NT$1000",
                    "長期目標（12個月）": "NT$1100",
                    "長期潛力（5年）": "NT$1500",
                    "信心指數": "6/10",
                }
            },
        },
    }
    context["parsed"] = ar.parse_structured_data(context)
    return context


def complete_v2_context():
    data = base_data()
    data.update({
        "ticker": "2449.TW",
        "company_name": "京元電子 / King Yuan Electronics Co., Ltd.",
        "current_price_fmt": "NT$309.50",
        "market_cap_fmt": "NT$3784.40億",
        "pe_ratio": "47.6x",
        "pb_ratio": "6.95x",
        "gross_margin": "37.4%",
        "roe": "17.6%",
        "dividend_yield": "1.24%",
        "beta": "0.91",
    })
    context = {
        "ticker": "2449.TW",
        "company_name": "京元電子 / King Yuan Electronics Co., Ltd.",
        "pipeline_id": "v2",
        "agent_sequence": (11, 12, 13, 14, 15, 16),
        "data": data,
        "analyses": {
            11: (
                "Chief Economist and Industry Strategist at a top Wall Street Macro Hedge Fund.\n"
                "Analyze 2449.TW regarding macro environment and industry cycle.\n"
                "* No target prices, buy/sell/hold recommendations.\n\n"
                "## 一、 總體經濟與政策影響\n"
                "AI 與高階測試需求帶來溫和順風。\n\n"
                "## 三、 宏觀定調結論\n"
                "未來 6-12 個月為【溫和順風】。"
            ),
            12: "## 一、 核心商業模式解析\n京元電子以半導體測試服務收費。",
            13: (
                "Forensic Accountant / Financial Risk Specialist.\n"
                "* No target price.\n"
                "Financial JSON and previous agent summaries.\n\n"
                "# 2449.TW 京元電子財務排雷與體質評估報告\n"
                "## 三、 財務紅旗總結\n"
                "財務體質評級：【尚可】。"
            ),
            14: "## 一、 未來 3-5 年成長驅動力預測\nAI/HPC 測試為核心成長來源。",
            15: "## 四、 交易動能總結\n資金動能評估：【中性】。",
            16: "## 一、 實戰交易邏輯 (Investment Thesis)\n採取持有並等待回檔。",
        },
        "structured_outputs": {
            12: {
                "moat_scores": {
                    "品牌影響力": 4,
                    "網路效應": 2,
                    "轉換成本": 7,
                    "成本優勢": 6,
                    "專利技術": 7,
                    "整體護城河": 5.2,
                }
            },
            14: {"price_targets": {"熊市情境": 182, "基本情境": 273, "牛市情境": 379}},
            16: {
                "recommendation": {
                    "建議": "持有",
                    "短期目標（3個月）": "NT$273",
                    "中期目標（6個月）": "NT$310",
                    "長期目標（12個月）": "NT$350",
                    "長期潛力（5年）": "NT$500",
                    "信心指數": "7/10",
                }
            },
        },
    }
    context["parsed"] = ar.parse_structured_data(context)
    return context


class AuditRuleTests(unittest.TestCase):
    def setUp(self):
        audit_repair.clear_repair_429_circuit()

    def assert_has_issue(self, issues, expected):
        joined = "\n".join(issues)
        self.assertIn(expected, joined)

    def test_financial_redline_regressions(self):
        cases = [
            (
                2,
                "ROA 23.6% × 權益乘數 1.252 = 29.5%，與 ROE 39.1% 的落差來自應付帳款營運槓桿。",
                {},
                "杜邦分析紅線",
            ),
            (
                2,
                "TTM 杜邦分析使用淨利率、資產周轉率與權益乘數，並解釋 ROE 差距。",
                {},
                "不可把 Yahoo TTM",
            ),
            (
                4,
                "DCF 估值下 Forward EPS 201.88 × 27x 與目標價完全吻合，是數學防呆。",
                {},
                "估值方法紅線",
            ),
            (
                4,
                "WACC 使用帳面 D/E 推算，權益權重高達95%。",
                {},
                "WACC 紅線",
            ),
            (
                2,
                "營收成長73%，FCF轉換率106%，代表現金流品質極佳。",
                {},
                "FCF 品質紅線",
            ),
            (
                5,
                "未來一年營收成長70%，因此長期淨利率仍可維持高檔。",
                {},
                "製造業情境紅線",
            ),
            (
                4,
                "Forward P/E 給予27x，Forward EPS 隱含營收需成長78%。",
                {},
                "雙重樂觀紅線",
            ),
            (
                2,
                "Yahoo 顯示營收年增率高達196.0%，可視為 TTM 營收成長。",
                {"yahoo_revenue_growth": "196.0%"},
                "成長率口徑紅線",
            ),
            (
                2,
                "公司淨利率22.8%，可直接用於正式估值。",
                {"profit_margin_provider": "22.8%", "profit_margin": "8.8%"},
                "淨利率口徑紅線",
            ),
            (
                2,
                "2025年營收為72.7B，TTM營收為99.79B，營收年增率高達196.0%。",
                {},
                "算術一致性紅線",
            ),
            (
                2,
                "TTM營收為99.79B，淨利率為22.8%。市值為612.41B，TTM P/E為69.8x。",
                {},
                "估值一致性紅線",
            ),
            (
                2,
                "ROE為39.1%，ROA為23.6%，權益乘數為1.252x，杜邦分析顯示獲利優異。",
                {},
                "杜邦數值一致性紅線",
            ),
        ]
        for agent_num, text, data, expected in cases:
            with self.subTest(expected=expected):
                issues = ar.validate_analysis_output(agent_num, text, data)
                self.assert_has_issue(issues, expected)

    def test_audit_allows_annual_dupont_with_ttm_caveat(self):
        text = (
            "根據 2025 同期間年度數據，年度杜邦恒等式為："
            "淨利率 12.0% × 資產周轉率 0.847x × 權益乘數 1.427x = ROE 14.5%。"
            "Yahoo TTM ROE 37.2% 與 ROA 12.9% 僅供對照，屬於不同期間平均資產計算之口徑偏差。"
        )
        issues = ar.validate_analysis_output(2, text, {})
        self.assertNotIn("杜邦分析紅線", "\n".join(issues))

    def test_confidence_calibration_caps_fresh_data_after_circuit_breaker(self):
        recommendation = {
            "confidence": "9/10",
            "confidence_basis": {
                "evidence_items": ["a", "b", "c"],
                "key_risks_acknowledged": ["x", "y"],
            },
        }

        without_circuit = build_confidence_calibration(recommendation, {"status": "fresh"}, circuit_ever_opened=False)
        with_circuit = build_confidence_calibration(recommendation, {"status": "fresh"}, circuit_ever_opened=True)

        self.assertEqual(without_circuit["max_recommended_confidence"], 10)
        self.assertEqual(with_circuit["max_recommended_confidence"], 8)
        self.assertTrue(with_circuit["circuit_ever_opened"])
        self.assertIn("修復機制", with_circuit["reasons"][0])

    def test_final_audit_critical_lint_flags_missing_target_price_in_final_output(self):
        context = complete_context()
        context["analyses"][7] = "## 最終投資決策\n投資建議：持有，等待基本面確認。"

        audit = ar.run_final_report_audit(context, append_section=False)

        self.assertIn("目標價", "\n".join(audit["critical"]))

    def test_generated_quality_warning_does_not_self_trigger_audit(self):
        text = (
            "根據 2025 同期間年度數據，年度杜邦恒等式為："
            "淨利率 12.0% × 資產周轉率 0.847x × 權益乘數 1.427x = ROE 14.5%。"
            "\n\n## 系統品質檢查警示\n"
            "- 杜邦分析紅線：不可把 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率或權益乘數拼接成 TTM 杜邦公式。"
        )
        issues = ar.validate_analysis_output(2, text, {})
        self.assertNotIn("杜邦分析紅線", "\n".join(issues))

    def test_prompt_and_identity_regressions(self):
        self.assert_has_issue(
            ar.validate_prompt_leakage("Senior Analyst at Goldman Sachs\n正式內容"),
            "內部提示詞片段",
        )
        self.assert_has_issue(
            ar.validate_prompt_leakage("Chief Economist and Industry Strategist\n正式內容"),
            "內部提示詞片段",
        )
        self.assert_has_issue(
            ar.validate_prompt_leakage("Senior Financial Media Host. Bull thesis 與 Bear thesis 開場。\n正式內容"),
            "內部提示詞片段",
        )
        self.assertNotIn(
            "Senior Financial Media Host",
            ar.sanitize_model_output("Senior Financial Media Host. Bull thesis 與 Bear thesis 開場。\n\n## 多空辯論\n正式內容"),
        )
        self.assert_has_issue(
            ar.validate_company_identity("大亞（1623.TW）是能源鏈整合服務商。大亞具備儲能業務。", base_data()),
            "公司身分錯置",
        )

    def test_sanitizers_remove_leaked_role_bylines_and_debate_prompt_blocks(self):
        leaked_debate = (
            "Bull (Dr. Chen) vs. Bear (Dr. Li) on 2449.TW (King Yuan Electronics).\n"
            "        *   Round 1: Fundamentals/Moat (Bull starts).\n"
            "        *   Fixed prefixes: 🐂 多頭: and 🐻 空頭:.\n"
            "        *   Use provided Target Prices and Growth Scenarios.\n\n"
            "歡迎收看今天的《財經大辯論》，我是主持人。\n\n"
            "### Round 1：基本面與護城河\n"
            "🐂 多頭：AI/HPC 測試需求提升，有利測試 ASP。\n"
            "🐻 空頭：高 CapEx 與負自由現金流仍需警惕。"
        )
        for sanitizer in (ar.sanitize_model_output, report_utils.sanitize_report_text):
            cleaned = sanitizer(leaked_debate)
            self.assertIn("歡迎收看", cleaned)
            self.assertIn("🐂 多頭", cleaned)
            self.assertNotIn("Bull (Dr. Chen)", cleaned)
            self.assertNotIn("Fixed prefixes", cleaned)
            self.assertNotIn("Use provided Target Prices", cleaned)

        byline = (
            "# 京元電子研究報告\n\n"
            "**分析師：** 高盛 (Goldman Sachs) 股票研究部門\n"
            "**研究對象：** 京元電子\n\n"
            "## 一、公司概述\n京元電子是半導體測試廠。"
        )
        cleaned = ar.sanitize_model_output(byline)
        self.assertNotIn("高盛", cleaned)
        self.assertIn("公司概述", cleaned)

    def test_v2_report_sanitizes_prompt_leak_and_inserts_structured_blocks(self):
        md = report_gen.generate_markdown_report(complete_v2_context())

        for header in [
            "## 1. 總經環境與產業週期 (Agent 11)",
            "## 2. 商業模式與競爭護城河 (Agent 12)",
            "## 3. 財務排雷與體質評估 (Agent 13)",
            "## 4. 估值模型與成長預測 (Agent 14)",
            "## 5. 籌碼流動與市場情緒 (Agent 15)",
            "## 6. 實戰交易決策 (Agent 16)",
        ]:
            self.assertIn(header, md)
        for leaked in [
            "Chief Economist and Industry Strategist",
            "Forensic Accountant",
            "No target price",
            "Financial JSON and previous agent summaries",
            "Analyze 2449.TW",
        ]:
            self.assertNotIn(leaked, md)

        self.assertIn("[護城河評分]", md)
        self.assertIn("整體護城河: 5.2/10", md)
        self.assertIn("[目標股價]", md)
        self.assertIn("基本情境: NT$273", md)
        self.assertIn("[投資建議]", md)
        self.assertIn("長期潛力（5年）：NT$500", md)

    def test_final_audit_detects_v2_prompt_leak(self):
        context = complete_v2_context()
        audit = ar.run_final_report_audit(context, append_section=False)
        joined = "\n".join(audit["critical"])
        self.assertIn("總經環境與產業週期: 輸出仍包含內部提示詞片段", joined)
        self.assertIn("財務排雷與體質評估: 輸出仍包含內部提示詞片段", joined)
        self.assertIn(11, audit["repair_agent_issues"])
        self.assertIn(13, audit["repair_agent_issues"])

    def test_final_audit_structured_and_target_rules(self):
        context = complete_context()
        context["structured_outputs"].pop(3)
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assert_has_issue(audit["critical"], "Agent 3 護城河評分 未提供可解析 JSON")
        self.assertIn(3, audit["repair_agent_issues"])

        context = complete_context()
        context["structured_outputs"][4] = {"price_targets": {"熊市情境": 3, "基本情境": 5, "牛市情境": 6}}
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assert_has_issue(audit["critical"], "目標價疑似單位縮小錯誤")
        self.assertIn(4, audit["repair_agent_issues"])

        context = complete_context()
        context["structured_outputs"][4] = {"price_targets": {"熊市情境": 1200, "基本情境": 1000, "牛市情境": 800}}
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assert_has_issue(audit["critical"], "三情境目標價順序不合理")

    def test_missing_and_failed_agents_are_repairable(self):
        context = complete_context()
        del context["analyses"][1]
        context["blocking_issues"] = ["Agent 1 商業模式與整體分析: 前次失敗"]
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assertIn(1, audit["repair_agent_issues"])

        with patch.object(ar, "run_single_agent", return_value="## 商業模式\n大東電以電線電纜為核心業務。"):
            ar.attempt_final_audit_repair(context, audit, object())

        self.assertIn(1, context["analyses"])
        self.assertNotIn("blocking_issues", context)
        self.assertTrue(any("商業模式與整體分析 AI 修復成功" in item for item in context["audit_repair_log"]))

        context = complete_context()
        context["analyses"][2] = "[Agent 2 執行失敗：所有模型/Key 不可用]"
        context["blocking_issues"] = ["Agent 2 五年財務深度分析: [Agent 2 執行失敗：所有模型/Key 不可用]"]
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assertIn(2, audit["repair_agent_issues"])

    def test_agent7_dupont_redline_can_repair_to_clean_report(self):
        context = complete_context()
        context["analyses"][7] = (
            "[投資建議]\n"
            "建議: 避免\n短期目標（3個月）: NT$2500\n中期目標（6個月）: NT$2300\n"
            "長期目標（12個月）: NT$2150\n長期潛力（5年）: NT$3500\n信心指數: 8/10\n"
            "[/投資建議]\n\n"
            "最終決策使用 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率及權益乘數拼接成 TTM 杜邦公式，"
            "並把差距解讀為應付帳款營運槓桿。"
        )
        context["parsed"] = ar.parse_structured_data(context)
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assertIn(7, audit["repair_agent_issues"])
        self.assert_has_issue(audit["critical"], "最終投資決策: 杜邦分析紅線")

        def repaired_agent(agent_num, data, ctx, rotator, max_retries=1):
            self.assertEqual(agent_num, 7)
            self.assertIn("前次退件反思摘要", ctx.get("_audit_reflection_instruction", ""))
            ctx["structured_outputs"][7] = {
                "recommendation": {
                    "建議": "避免",
                    "短期目標（3個月）": "NT$950",
                    "中期目標（6個月）": "NT$900",
                    "長期目標（12個月）": "NT$850",
                    "長期潛力（5年）": "NT$1100",
                    "信心指數": "8/10",
                }
            }
            return (
                "## 最終投資決策\n"
                "投資建議：避免。目標價：3 個月 NT$950、6 個月 NT$900、12 個月 NT$850。"
                "杜邦分析僅引用同期間年度杜邦恒等式，"
                "Yahoo TTM ROE/ROA 僅作資料品質警示，不進行跨期拼接。"
            )

        with patch.object(ar, "run_single_agent", side_effect=repaired_agent):
            ar.attempt_final_audit_repair(context, audit, object())

        context["parsed"] = ar.parse_structured_data(context)
        final_audit = ar.run_final_report_audit(context, append_section=False)
        self.assertEqual(final_audit["status"], "passed")
        context["final_audit"] = final_audit
        html = report_gen.generate_html_report(context)
        self.assertNotIn("系統異常提醒", html)
        self.assertNotIn("系統品質檢查警示", html)

    def test_finalize_audit_retries_until_reaudit_passes(self):
        context = complete_context()
        bad_agent7 = (
            "## 最終投資決策\n"
            "TTM 杜邦分析使用 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率及權益乘數拼接，"
            "並解釋口徑差距。"
        )
        context["analyses"][7] = bad_agent7
        context["parsed"] = ar.parse_structured_data(context)
        repair_calls = []

        def staged_repair(agent_num, data, ctx, rotator, issues):
            self.assertEqual(agent_num, 7)
            repair_calls.append(list(issues))
            if len(repair_calls) == 1:
                ctx["analyses"][7] = bad_agent7
                return False, "第一次重寫仍未修正杜邦紅線"

            ctx["structured_outputs"][7] = {
                "recommendation": {
                    "建議": "持有",
                    "短期目標（3個月）": "NT$900",
                    "中期目標（6個月）": "NT$1000",
                    "長期目標（12個月）": "NT$1100",
                    "長期潛力（5年）": "NT$1500",
                    "信心指數": "6/10",
                }
            }
            ctx["analyses"][7] = (
                "## 最終投資決策\n"
                "投資建議：持有。目標價：3 個月 NT$900、6 個月 NT$1000、12 個月 NT$1100。"
                "杜邦分析僅引用同期間年度杜邦恒等式；"
                "Yahoo TTM ROE/ROA 僅列為資料品質警示，不跨期拼接。"
            )
            return True, "第二次重寫後通過品質檢查"

        with patch.object(ar, "_repair_agent_output", side_effect=staged_repair):
            audit = ar.finalize_final_audit(context, object(), max_repair_passes=2)

        self.assertEqual(audit["status"], "passed")
        self.assertEqual(len(repair_calls), 2)
        html = report_gen.generate_html_report(context)
        self.assertNotIn("系統異常提醒", html)

    def test_finalize_audit_preserves_report_when_repair_still_fails(self):
        context = complete_context()
        context["analyses"][7] = (
            "## 最終投資決策\n"
            "TTM 杜邦分析使用 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率及權益乘數拼接，"
            "並解釋口徑差距。"
        )
        context["parsed"] = ar.parse_structured_data(context)

        with patch.object(ar, "_repair_agent_output", return_value=(False, "模型仍輸出錯誤")):
            audit = ar.finalize_final_audit(context, object(), max_repair_passes=1)

        self.assertEqual(audit["status"], "needs_attention")
        self.assertTrue(audit["report_preserved"])
        self.assertTrue(any("報告會保留" in item for item in context["audit_repair_log"]))
        html = report_gen.generate_html_report(context)
        self.assertIn("系統異常提醒", html)
        self.assertIn("本報告已保留供檢視", html)

    def test_final_audit_marks_future_price_history_as_correction(self):
        context = complete_context()
        context["data"]["price_history"] = {"2999-01-01": 123}
        audit = ar.run_final_report_audit(context, append_section=False)
        self.assert_has_issue(audit["corrections"], "歷史股價含未來日期")

    def test_passed_audit_corrections_do_not_render_abnormal_banner(self):
        context = complete_context()
        context["final_audit"] = {
            "status": "passed",
            "critical": [],
            "warnings": [],
            "corrections": ["資料源口徑已校正"],
            "report_preserved": True,
        }
        context["audit_repair_log"] = ["商業模式與整體分析 AI 修復成功：已重寫並通過品質檢查"]
        self.assertEqual(report_gen.build_audit_sections(context), [])
        self.assertEqual(report_gen.build_audit_banner_html(context), "")

    def test_previous_context_uses_relevant_slices_instead_of_full_context(self):
        long_agent_1 = "## 商業模式\n" + ("完整內容A" * 1600)
        long_agent_2 = "## 財務分析\n" + ("完整內容B" * 1600)
        context = {
            "analyses": {1: long_agent_1, 2: long_agent_2},
            "context_digests": {4: '{"decision_relevant_facts":["摘要"]}'},
        }

        formatted = ar._format_previous(context, 4)

        self.assertIn("【提煉 Agent 結構化摘要】", formatted)
        self.assertIn("【前序分析精選片段（非全文，依下一位 Agent 任務檢索）】", formatted)
        self.assertIn("系統已依 Agent 4 任務精選前序片段", formatted)
        self.assertIn("完整內容A" * 20, formatted)
        self.assertIn("完整內容B" * 20, formatted)
        self.assertNotIn("完整前序分析（未截斷）", formatted)
        self.assertLess(len(formatted), len(long_agent_1) + len(long_agent_2))

    def test_financial_prompt_is_clean_json_with_tool_results(self):
        data = base_data()
        data.update({
            "sector": "科技業",
            "industry": "電子零組件",
            "country": "Taiwan",
            "employees": 1000,
            "market_cap_raw": 100_000_000_000,
            "week_52_high": 120,
            "week_52_low": 80,
            "pe_ratio_raw": 20,
            "forward_pe_raw": 15,
            "pb_ratio": "2.0x",
            "ps_ratio": "3.0x",
            "ev_ebitda": "8.0x",
            "shares_raw": 1_000_000_000,
            "trailing_eps": 5,
            "forward_eps": 6,
            "revenue_ttm_raw": 20_000_000_000,
            "net_income_ttm_raw": 2_000_000_000,
            "net_income_ttm_source": "trailing EPS × shares",
            "ebitda_raw": 3_000_000_000,
            "gross_margin_raw": 0.25,
            "operating_margin_raw": 0.12,
            "profit_margin_raw": 0.10,
            "profit_margin_provider_raw": 0.11,
            "free_cash_flow_raw": 1_500_000_000,
            "operating_cash_flow_raw": 2_500_000_000,
            "total_debt_raw": 5_000_000_000,
            "total_cash_raw": 2_000_000_000,
            "debt_to_equity": "5.0%",
            "current_ratio": "2.0",
            "years": ["2023", "2024", "2025"],
            "revenue_history": [10, 15, 20],
            "net_income_history": [1, 1.5, 2],
            "gross_profit_history": [2.5, 3.5, 5],
            "operating_income_history": [1, 1.8, 2.4],
            "fcf_history": [0.8, 1.0, 1.5],
            "gross_margin_history": [25, 23.3, 25],
            "op_margin_history": [10, 12, 12],
            "net_margin_history": [10, 10, 10],
            "roe_history": [8, 9, 10],
            "total_assets_history": [20, 24, 28],
            "total_equity_history": [12, 15, 18],
            "latest_annual_revenue_growth": "33.3%",
            "latest_annual_net_income_growth": "33.3%",
            "ttm_vs_latest_annual_revenue_change": "0.0%",
            "yahoo_revenue_growth": "12.0%",
            "yahoo_earnings_growth": "10.0%",
            "revenue_cagr_5yr": "41.4%",
            "peer_discovery_results": [{"title": "global peers", "source_type": "google_peer_discovery"}],
        })

        prompt = financial_data.format_data_for_prompt(data)
        payload_text = prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
        payload = json.loads(payload_text)

        self.assertEqual(payload["unit_contract"]["money"], "billion_twd")
        self.assertEqual(payload["market_data"]["market_cap_billion_twd"], 100.0)
        self.assertEqual(payload["ttm_financials"]["revenue_billion_twd"], 20.0)
        self.assertIn("deterministic_financial_tool_results", payload)
        self.assertIn("revenue_cagr", payload["deterministic_financial_tool_results"]["calculations"])
        self.assertIn("market_catalysts", payload)
        self.assertIn("institutional_trading", payload)
        self.assertIn("peer_context", payload)
        self.assertEqual(payload["peer_context"]["search_discovery_results"][0]["source_type"], "google_peer_discovery")
        self.assertIn("local_valuation_context", payload)
        self.assertNotIn("不可原諒", prompt)
        self.assertNotIn("⚠️【單位與邏輯防呆", prompt)

    def test_financial_tool_calculations(self):
        cagr = financial_tools.calculate_cagr(10, 20, 2)
        self.assertAlmostEqual(cagr["cagr_pct"], 41.4214, places=4)

        wacc = financial_tools.calculate_wacc(
            market_cap_twd=95_000_000_000,
            total_debt_twd=5_000_000_000,
            cost_of_equity_pct=10,
            cost_of_debt_pct=4,
            tax_rate_pct=20,
        )
        self.assertEqual(wacc["equity_weight_pct"], 95.0)
        self.assertAlmostEqual(wacc["wacc_pct"], 9.66, places=2)

        dcf = financial_tools.calculate_dcf(
            base_fcf_billion_twd=1,
            growth_rate_pct=5,
            wacc_pct=10,
            terminal_growth_pct=2,
            shares_outstanding=100_000_000,
        )
        self.assertGreater(dcf["price_per_share_twd"], 100)

        ddm = financial_tools.calculate_ddm(
            dividend_per_share_twd=5,
            cost_of_equity_pct=8,
            dividend_growth_pct=2,
        )
        self.assertAlmostEqual(ddm["value_per_share_twd"], 85.0, places=2)

    def test_quant_engine_records_fallback_fields_and_warning(self):
        metrics = QuantEngine.compute_all({
            "current_price": 100,
            "shares_outstanding": 100,
            "total_debt": 500,
            "tax_rate": 0.20,
            "free_cash_flows": [100, 110, 120, 130, 140],
            "eps": 5,
        })

        self.assertIn("total_equity", metrics["fallback_fields"])
        self.assertTrue(metrics["data_quality_warning"])

    def test_agent7_prompt_requires_quant_fallback_data_warning(self):
        self.assertIn("quant_metrics", ar.SYSTEM_PROMPTS[7])
        self.assertIn("【資料警示】", ar.SYSTEM_PROMPTS[7])
        self.assertIn("__has_fallback=True", ar.SYSTEM_PROMPTS[7])

    def test_wacc_defaults_are_consistent_across_calculators(self):
        tool_wacc = financial_tools.calculate_wacc(95_000_000_000, 5_000_000_000)
        quant_wacc_pct = QuantEngine.calculate_wacc(
            95_000_000_000,
            5_000_000_000,
            config.WACC_COST_OF_EQUITY_DEFAULT_PCT / 100,
            config.WACC_COST_OF_DEBT_DEFAULT_PCT / 100,
            config.WACC_TAX_RATE_DEFAULT_PCT / 100,
        ) * 100

        self.assertLess(abs(tool_wacc["wacc_pct"] - quant_wacc_pct), 0.0001)

    def test_final_audit_warns_on_dual_dcf_conflict(self):
        context = complete_context()
        context["data"]["quant_metrics"] = {"dcf_intrinsic_value": 100.0}
        context["analyses"][4] = (
            "## 估值\n"
            "DCF 模型顯示基本情境目標價 NT$200，與市場價格相比仍有上行空間。"
        )
        context["parsed"] = ar.parse_structured_data(context)

        audit = ar.run_final_report_audit(context, append_section=False)

        self.assert_has_issue(audit["warnings"], "DCF 來源衝突")

    def test_agent_function_tools_are_registered(self):
        self.assertEqual([tool.__name__ for tool in ar.get_agent_function_tools(2)], ["calculate_cagr"])
        self.assertEqual([tool.__name__ for tool in ar.get_agent_function_tools(3)], ["calculate_dupont"])
        self.assertEqual([tool.__name__ for tool in ar.get_agent_function_tools(12)], ["calculate_dupont"])
        self.assertEqual(
            [tool.__name__ for tool in ar.get_agent_function_tools(13)],
            ["calculate_cagr", "calculate_dupont"],
        )
        self.assertEqual(
            [tool.__name__ for tool in ar.get_agent_function_tools(18)],
            ["calculate_cagr", "calculate_dupont"],
        )
        self.assertEqual(
            [tool.__name__ for tool in ar.get_agent_function_tools(4)],
            [
                "calculate_cagr",
                "calculate_wacc",
                "calculate_dcf",
                "calculate_ddm",
                "calculate_implied_revenue_growth",
            ],
        )
        self.assertEqual(
            [tool.__name__ for tool in ar.get_agent_function_tools(14)],
            [
                "calculate_cagr",
                "calculate_wacc",
                "calculate_dcf",
                "calculate_ddm",
                "calculate_implied_revenue_growth",
            ],
        )

    def test_implied_revenue_growth_tool_reverse_engineers_forward_eps(self):
        result = financial_tools.calculate_implied_revenue_growth(
            target_eps_twd=20,
            current_net_margin_pct=10,
            shares_outstanding=1_000_000_000,
            current_revenue_billion_twd=100,
            forecast_years=2,
        )

        self.assertEqual(result["required_revenue_billion_twd"], 200.0)
        self.assertEqual(round(result["implied_revenue_cagr_pct"], 2), 41.42)

    def test_implied_revenue_growth_tool_rejects_fractional_forecast_years(self):
        result = financial_tools.calculate_implied_revenue_growth(
            target_eps_twd=20,
            current_net_margin_pct=10,
            shares_outstanding=1_000_000_000,
            current_revenue_billion_twd=100,
            forecast_years=1.5,
        )

        self.assertEqual(result, {"error": "forecast_years must be a positive integer"})

    def test_valuation_agents_register_implied_growth_tool(self):
        self.assertIn(
            "calculate_implied_revenue_growth",
            [tool.__name__ for tool in ar.get_agent_function_tools(4)],
        )
        self.assertIn(
            "calculate_implied_revenue_growth",
            [tool.__name__ for tool in ar.get_agent_function_tools(14)],
        )

    def test_valuation_rules_require_implied_growth_tool_for_extreme_forward_eps(self):
        rules = json.loads(
            (ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8")
        )

        for agent_num in ("4", "14"):
            valuation_rules = rules["numeric_tool_instructions"][agent_num]["rules"]
            self.assertTrue(
                any(
                    "calculate_implied_revenue_growth" in rule
                    and "implied_revenue_cagr_pct" in rule
                    for rule in valuation_rules
                )
            )
        self.assertNotIn("絕對禁止自行計算", ar.ANALYSIS_PROMPTS[4])
        self.assertIn("工具呼叫", ar.ANALYSIS_PROMPTS[4])

    def test_structured_agents_use_native_response_schema(self):
        config_obj = ar.build_generation_config(3, "system")
        self.assertEqual(getattr(config_obj, "response_mime_type", None), "application/json")
        self.assertIsNotNone(getattr(config_obj, "response_schema", None))
        v2_config_obj = ar.build_generation_config(14, "system")
        self.assertEqual(getattr(v2_config_obj, "response_mime_type", None), "application/json")
        self.assertIsNotNone(getattr(v2_config_obj, "response_schema", None))
        v3_config_obj = ar.build_generation_config(19, "system")
        self.assertEqual(getattr(v3_config_obj, "response_mime_type", None), "application/json")
        self.assertIsNotNone(getattr(v3_config_obj, "response_schema", None))

    def test_structured_schema_omits_additional_properties_for_genai(self):
        schema = structured_outputs.MoatStructuredOutput.model_json_schema(by_alias=True)
        self.assertNotIn("additionalProperties", json.dumps(schema, ensure_ascii=False))

    def test_generation_config_schema_omits_genai_rejected_numeric_bounds(self):
        config_obj = ar.build_generation_config(14, "system")
        schema_text = json.dumps(getattr(config_obj, "response_schema", {}), ensure_ascii=False)

        self.assertNotIn("exclusiveMinimum", schema_text)
        self.assertNotIn("exclusiveMaximum", schema_text)

    def test_structured_generation_config_does_not_mix_tools_with_json_schema(self):
        config_obj = ar.build_generation_config(14, "system")

        self.assertEqual(getattr(config_obj, "response_mime_type", None), "application/json")
        self.assertIsNotNone(getattr(config_obj, "response_schema", None))
        self.assertFalse(getattr(config_obj, "tools", None))
        self.assertFalse(getattr(config_obj, "automatic_function_calling", None))

    def test_openai_structured_output_schema_is_strict_without_changing_genai_schema(self):
        genai_schema = PriceTargetStructuredOutput.model_json_schema(by_alias=True)
        openai_format = openai_json_schema_response_format("price_target", PriceTargetStructuredOutput)

        self.assertNotIn("additionalProperties", json.dumps(genai_schema, ensure_ascii=False))
        self.assertEqual(openai_format["type"], "json_schema")
        self.assertIs(openai_format["json_schema"]["strict"], True)
        self.assertIn(
            '"additionalProperties": false',
            json.dumps(openai_format, ensure_ascii=False),
        )

    def test_openai_structured_output_adapter_requires_all_fields_and_valid_name(self):
        schema = openai_json_schema_response_format(
            "price_target",
            PriceTargetStructuredOutput,
        )["json_schema"]["schema"]
        pending = [schema]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                    self.assertEqual(set(node.get("required", [])), set(node.get("properties", {})))
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)

        with self.assertRaises(ValueError):
            openai_json_schema_response_format("invalid schema name!", PriceTargetStructuredOutput)

    def test_structured_schemas_include_reasoning_fields(self):
        moat_schema = structured_outputs.MoatStructuredOutput.model_json_schema(by_alias=True)
        price_schema = structured_outputs.PriceTargetStructuredOutput.model_json_schema(by_alias=True)
        recommendation_schema = structured_outputs.RecommendationStructuredOutput.model_json_schema(by_alias=True)

        self.assertIn("reasoning_steps", json.dumps(moat_schema, ensure_ascii=False))
        self.assertIn("dcf_reasoning", json.dumps(price_schema, ensure_ascii=False))
        self.assertIn("peer_reasoning", json.dumps(price_schema, ensure_ascii=False))
        self.assertIn("scenario_reasoning", json.dumps(price_schema, ensure_ascii=False))
        self.assertIn("reasoning_steps", json.dumps(recommendation_schema, ensure_ascii=False))
        bubble_schema = structured_outputs.BubbleSniperStructuredOutput.model_json_schema(by_alias=True)
        self.assertIn("強烈放空", json.dumps(bubble_schema, ensure_ascii=False))

    def test_pipeline_v2_definition_and_prompt_registration(self):
        v2 = pipeline_modes.get_pipeline_definition("v2")
        self.assertEqual(v2["agents"], (11, 12, 13, 20, 14, 15, 21, 16))
        self.assertEqual(v2["structured_agents"], {"moat": 12, "valuation": 14, "recommendation": 16})
        for agent_num in v2["agents"]:
            self.assertIn(agent_num, ar.AGENT_NAMES)
            self.assertIn(agent_num, ar.SYSTEM_PROMPTS)
            self.assertIn(agent_num, ar.ANALYSIS_PROMPTS)
            self.assertIn(agent_num, ar.AGENT_MODELS)

    def test_pipeline_v3_definition_and_prompt_registration(self):
        v3 = pipeline_modes.get_pipeline_definition("v3")
        self.assertEqual(v3["agents"], (17, 18, 20, 21, 19))
        self.assertEqual(v3["groups"], ((17,), (18, 20), (21,), (19,)))
        self.assertEqual(v3["structured_agents"], {"recommendation": 19})
        self.assertEqual(pipeline_modes.normalize_pipeline_id("mode_c"), "v3")
        for agent_num in v3["agents"]:
            self.assertIn(agent_num, ar.AGENT_NAMES)
            self.assertIn(agent_num, ar.SYSTEM_PROMPTS)
            self.assertIn(agent_num, ar.ANALYSIS_PROMPTS)
            self.assertIn(agent_num, ar.AGENT_MODELS)
        self.assertIn("Traditional Chinese", ar.SYSTEM_PROMPTS[19])
        self.assertIn("強烈放空", ar.SYSTEM_PROMPTS[19])

    def test_dual_pipeline_run_mode_sequence(self):
        self.assertEqual(pipeline_modes.normalize_pipeline_run_id("both"), "both")
        self.assertEqual(pipeline_modes.normalize_pipeline_run_id("a+b"), "both")
        self.assertEqual(pipeline_modes.normalize_pipeline_run_id("a+b+c"), "both")
        self.assertEqual(pipeline_modes.get_pipeline_run_sequence("both"), ("v1", "v2", "v3"))
        self.assertEqual(pipeline_modes.get_pipeline_run_agent_total("both"), 23)
        self.assertEqual(pipeline_modes.get_pipeline_run_sequence("v2"), ("v2",))
        self.assertEqual(pipeline_modes.get_pipeline_run_sequence("v3"), ("v3",))

    def test_pipeline_v2_parses_structured_outputs_and_renders_sections(self):
        context = {
            "pipeline_id": "v2",
            "agent_sequence": (11, 12, 13, 14, 15, 16),
            "data": base_data(),
            "analyses": {
                11: "## 總經\n中性。",
                12: "## 護城河\n中等。",
                13: "## 財務排雷\n尚可。",
                14: "## 估值\n基本情境 NT$1000。",
                15: "## 籌碼\n偏多。",
                16: "## 實戰決策\n持有。",
            },
            "structured_outputs": {
                12: {
                    "moat_scores": {
                        "品牌影響力": 4,
                        "網路效應": 2,
                        "轉換成本": 5,
                        "成本優勢": 6,
                        "專利技術": 4,
                        "整體護城河": 5,
                    }
                },
                14: {"price_targets": {"熊市情境": 800, "基本情境": 1000, "牛市情境": 1200}},
                16: {
                    "recommendation": {
                        "建議": "持有",
                        "短期目標（3個月）": "NT$900",
                        "中期目標（6個月）": "NT$1000",
                        "長期目標（12個月）": "NT$1100",
                        "長期潛力（5年）": "NT$1500",
                        "信心指數": "6/10",
                    }
                },
            },
        }

        parsed = ar.parse_structured_data(context)
        context["parsed"] = parsed
        sections = report_gen.build_agent_sections(context, html=False)
        markdown = report_gen.generate_markdown_report(context)

        self.assertEqual(parsed["price_targets"]["基本情境"], 1000)
        self.assertEqual(parsed["recommendation"]["建議"], "持有")
        self.assertEqual([section["agent_num"] for section in sections], [11, 12, 13, 14, 15, 16])
        self.assertIn("實戰交易決策報告", markdown)
        self.assertIn("## 6. 實戰交易決策 (Agent 16)", markdown)

    def test_pipeline_v3_parses_recommendation_without_moat_or_valuation(self):
        context = {
            "pipeline_id": "v3",
            "agent_sequence": (17, 18, 19),
            "data": base_data(),
            "analyses": {
                17: "## 泡沫情緒\nFOMO 過熱。",
                18: "## 法證財務\n法人高檔派發。",
                19: "## 泡沫狙擊\n## 做空觸發條件（Catalyst for crash）\n財測下修。\n\n## 防軋空停損點（Stop-loss level）\n突破前高。",
            },
            "structured_outputs": {
                19: {
                    "recommendation": {
                        "建議": "強烈放空",
                        "短期目標（3個月）": "NT$700",
                        "中期目標（6個月）": "NT$600",
                        "長期目標（12個月）": "NT$500",
                        "長期潛力（5年）": "NT$650",
                        "信心指數": "8/10",
                    }
                },
            },
        }

        parsed = ar.parse_structured_data(context)
        context["parsed"] = parsed
        sections = report_gen.build_agent_sections(context, html=False)
        markdown = report_gen.generate_markdown_report(context)

        self.assertEqual(parsed["recommendation"]["建議"], "強烈放空")
        self.assertEqual(parsed["moat_scores"], {})
        self.assertEqual(parsed["price_targets"], {})
        self.assertEqual([section["agent_num"] for section in sections], [17, 18, 19])
        self.assertIn("泡沫狙擊研究報告", markdown)
        self.assertIn("## 3. 泡沫狙擊報告 (Agent 19)", markdown)

    def test_pipeline_v3_final_section_keeps_investment_block_at_tail(self):
        context = {
            "pipeline_id": "v3",
            "agent_sequence": (17, 18, 19),
            "data": base_data(),
            "analyses": {
                17: "## 泡沫情緒\nFOMO 過熱。",
                18: "## 法證財務\n法人高檔派發。",
                19: (
                    "[投資建議]\n"
                    "建議：強烈放空\n"
                    "短期目標（3個月）：NT$700\n"
                    "中期目標（6個月）：NT$600\n"
                    "長期目標（12個月）：NT$500\n"
                    "長期潛力（5年）：NT$650\n"
                    "信心指數：8/10\n"
                    "[/投資建議]\n\n"
                    "## 一、泡沫狙擊結論\\n市場題材已超前基本面。"
                ),
            },
            "structured_outputs": {
                19: {
                    "analysis_markdown": "## 一、泡沫狙擊結論\\n市場題材已超前基本面。",
                    "recommendation": {
                        "建議": "強烈放空",
                        "短期目標（3個月）": "NT$700",
                        "中期目標（6個月）": "NT$600",
                        "長期目標（12個月）": "NT$500",
                        "長期潛力（5年）": "NT$650",
                        "信心指數": "8/10",
                    },
                    "scenario_triggers": [
                        {"trigger_condition": "財測下修", "action": "提高避險部位", "direction": "bearish_downgrade"},
                        {"trigger_condition": "突破前高", "action": "回補空單並觀望", "direction": "neutral_review"},
                    ],
                },
            },
        }

        context["parsed"] = ar.parse_structured_data(context)
        section = report_gen.build_agent_sections(context, html=False)[-1]

        self.assertIn("## 一、泡沫狙擊結論\n市場題材已超前基本面。", section["body"])
        self.assertIn("## 做空觸發條件（Catalyst for crash）", section["body"])
        self.assertIn("財測下修", section["body"])
        self.assertIn("## 防軋空停損點（Stop-loss level）", section["body"])
        self.assertIn("突破前高", section["body"])
        self.assertLess(section["body"].index("## 一、泡沫狙擊結論"), section["body"].index("[投資建議]"))
        self.assertTrue(section["body"].rstrip().endswith("[/投資建議]"))

    def test_pipeline_v3_final_audit_requires_contrarian_risk_sections(self):
        context = {
            "pipeline_id": "v3",
            "agent_sequence": (17, 18, 19),
            "data": base_data(),
            "analyses": {
                17: "## 泡沫情緒\nFOMO 過熱。",
                18: "## 法證財務\n法人高檔派發。",
                19: "## 一、泡沫狙擊結論\n市場題材已超前基本面。",
            },
            "structured_outputs": {},
        }
        context["parsed"] = ar.parse_structured_data(context)

        audit = ar.run_final_report_audit(context, append_section=False)

        self.assertIn("缺少做空觸發條件", "\n".join(audit["critical"]))
        self.assertIn("缺少防軋空停損點", "\n".join(audit["critical"]))

    def test_normalized_structured_outputs_preserve_reasoning_without_polluting_prices(self):
        moat = structured_outputs.normalize_structured_output(3, {
            "reasoning_steps": ["品牌證據支持 6 分", "轉換成本較強", "網路效應偏弱"],
            "moat_scores": {
                "品牌影響力": 6,
                "網路效應": 3,
                "轉換成本": 7,
                "成本優勢": 6,
                "專利技術": 5,
                "整體護城河": 6,
            },
            "analysis_markdown": "正文",
        })
        self.assertEqual(moat["reasoning_steps"][0], "品牌證據支持 6 分")

        valuation = structured_outputs.normalize_structured_output(4, {
            "price_targets": {
                "dcf_reasoning": "normalized FCF 搭配市場價值 WACC。",
                "peer_reasoning": "同業倍數只作交叉檢查。",
                "scenario_reasoning": "熊市折讓需求下修，牛市反映產能開出。",
                "熊市情境": 800,
                "基本情境": 1000,
                "牛市情境": 1200,
            },
            "valuation_summary": {
                "primary_method": "blended",
                "uses_market_value_wacc": True,
                "uses_normalized_fcf": True,
                "double_counting_check": "未重複計價高成長。",
            },
            "analysis_markdown": "正文",
        })
        self.assertEqual(set(valuation["price_targets"].keys()), {"熊市情境", "基本情境", "牛市情境"})
        self.assertEqual(valuation["valuation_reasoning"]["dcf_reasoning"], "normalized FCF 搭配市場價值 WACC。")

        recommendation = structured_outputs.normalize_structured_output(7, {
            "reasoning_steps": ["估值合理", "風險仍高", "空方指出下修風險"],
            "recommendation": {
                "建議": "持有",
                "短期目標（3個月）": "NT$900",
                "中期目標（6個月）": "NT$1000",
                "長期目標（12個月）": "NT$1100",
                "長期潛力（5年）": "NT$1500",
                "信心指數": "6/10",
            },
            "confidence_basis": {
                "evidence_items": ["估值位於區間內", "現金流資料可用", "籌碼未明顯惡化"],
                "key_risks_acknowledged": ["需求下修", "估值收縮"],
                "data_gaps": [],
            },
            "scenario_triggers": [
                {"trigger_condition": "季度毛利率低於歷史區間", "action": "下調建議等級", "direction": "bearish_downgrade"},
                {"trigger_condition": "營收連續兩季優於預期", "action": "重新評估假設", "direction": "neutral_review"},
            ],
            "analysis_markdown": "正文",
        })
        self.assertIn("空方指出下修風險", recommendation["reasoning_steps"])

        bubble_recommendation = structured_outputs.normalize_structured_output(19, {
            "reasoning_steps": ["題材過熱", "財務現實不支持", "籌碼轉為派發"],
            "recommendation": {
                "建議": "強烈放空",
                "短期目標（3個月）": "NT$700",
                "中期目標（6個月）": "NT$600",
                "長期目標（12個月）": "NT$500",
                "長期潛力（5年）": "NT$650",
                "信心指數": "8/10",
            },
            "confidence_basis": {
                "evidence_items": ["P/E 河流圖高檔", "毛利率落後同業", "外資連續賣超"],
                "key_risks_acknowledged": ["政策利多軋空", "資料延遲"],
                "data_gaps": [],
            },
            "scenario_triggers": [
                {"trigger_condition": "下一次法說會下修全年財測", "action": "提高避險部位", "direction": "bearish_downgrade"},
                {"trigger_condition": "股價放量突破前波停損價", "action": "回補空單並觀望", "direction": "neutral_review"},
            ],
            "analysis_markdown": "## 做空觸發條件（Catalyst for crash）\n財測下修。\n\n## 防軋空停損點（Stop-loss level）\n突破前高。",
        })
        self.assertEqual(bubble_recommendation["recommendation"]["建議"], "強烈放空")
        report_text = structured_outputs.structured_output_to_report_text(19, bubble_recommendation)
        self.assertTrue(report_text.endswith("[/投資建議]"))
        self.assertIn("建議：強烈放空", report_text)

    def test_agent19_renderer_inserts_required_sections_before_tail_block(self):
        bubble_recommendation = structured_outputs.normalize_structured_output(19, {
            "reasoning_steps": ["題材過熱", "財務現實不支持", "籌碼轉為派發"],
            "recommendation": {
                "建議": "避免",
                "短期目標（3個月）": "NT$80",
                "中期目標（6個月）": "NT$70",
                "長期目標（12個月）": "NT$60",
                "長期潛力（5年）": "NT$75",
                "信心指數": "7/10",
            },
            "confidence_basis": {
                "evidence_items": ["P/E 河流圖高檔", "毛利率落後同業", "外資連續賣超"],
                "key_risks_acknowledged": ["政策利多軋空", "資料延遲"],
                "data_gaps": [],
            },
            "scenario_triggers": [
                {"trigger_condition": "下一次法說會下修全年財測", "action": "提高避險部位", "direction": "bearish_downgrade"},
                {"trigger_condition": "股價放量突破前波高點", "action": "回補空單並觀望", "direction": "neutral_review"},
            ],
            "analysis_markdown": "## 一、泡沫狙擊結論\\n市場題材已超前基本面。",
        })

        report_text = structured_outputs.structured_output_to_report_text(19, bubble_recommendation)

        self.assertIn("## 一、泡沫狙擊結論\n市場題材已超前基本面。", report_text)
        self.assertIn("## 做空觸發條件（Catalyst for crash）", report_text)
        self.assertIn("下一次法說會下修全年財測", report_text)
        self.assertIn("## 防軋空停損點（Stop-loss level）", report_text)
        self.assertIn("股價放量突破前波高點", report_text)
        self.assertLess(report_text.index("## 防軋空停損點（Stop-loss level）"), report_text.index("[投資建議]"))
        self.assertTrue(report_text.rstrip().endswith("[/投資建議]"))

    def test_agent19_deterministic_fallback_outputs_required_contract(self):
        context = {
            "pipeline_id": "v3",
            "analyses": {19: "Agent 19 未提供可解析 JSON。"},
            "structured_outputs": {},
        }

        ok, message = _deterministic_structured_fallback(19, {"current_price": 100.0}, context, "")
        text = context["analyses"][19]

        self.assertTrue(ok)
        self.assertIn("泡沫狙擊 fallback", message)
        self.assertIn("## 做空觸發條件（Catalyst for crash）", text)
        self.assertIn("## 防軋空停損點（Stop-loss level）", text)
        self.assertIn("建議：避免", text)
        self.assertTrue(text.rstrip().endswith("[/投資建議]"))

    def test_incomplete_structured_outputs_are_rejected_before_report_contract(self):
        self.assertIsNone(structured_outputs.normalize_structured_output(3, {
            "moat_scores": {
                "品牌影響力": 6,
                "網路效應": 3,
                "轉換成本": 7,
                "成本優勢": 6,
                "專利技術": 5,
                "整體護城河": 6,
            },
            "analysis_markdown": "正文",
        }))

        self.assertIsNone(structured_outputs.normalize_structured_output(4, {
            "price_targets": {
                "dcf_reasoning": "normalized FCF 搭配市場價值 WACC。",
                "熊市情境": 800,
                "基本情境": 1000,
                "牛市情境": 1200,
            },
            "analysis_markdown": "正文",
        }))

        self.assertIsNone(structured_outputs.normalize_structured_output(7, {
            "reasoning_steps": ["估值合理", "風險仍高", "空方指出下修風險"],
            "recommendation": {
                "建議": "持有",
                "短期目標（3個月）": "NT$900",
                "中期目標（6個月）": "NT$1000",
                "信心指數": "6/10",
            },
            "analysis_markdown": "正文",
        }))

    def test_agent_5_context_skips_agent_4_to_avoid_valuation_anchoring(self):
        context = {
            "analyses": {
                1: "Agent 1 商業模式。",
                2: "Agent 2 FCF 轉換率 80%。",
                3: "Agent 3 護城河弱項是網路效應。",
                4: "Agent 4 基本情境目標價 NT$1000。",
                5: "Agent 5 成長情境。",
            }
        }

        agent_5_context = ar._format_previous(context, 5)
        agent_6_context = ar._format_previous(context, 6)

        self.assertIn("Agent 2 FCF 轉換率", agent_5_context)
        self.assertNotIn("Agent 4 基本情境目標價", agent_5_context)
        self.assertIn("Agent 4 基本情境目標價", agent_6_context)

    def test_context_digest_fallback_contains_hard_metric_slots(self):
        payload = assistant_tasks._fallback_context_digest_payload(
            4,
            {"analyses": {1: "商業模式"}, "structured_outputs": {}},
            reason="test",
        )
        self.assertIn("hard_metrics", payload)
        self.assertIn("agent_2_fcf_conversion_rate", payload["hard_metrics"])
        self.assertIn("moat_weakness_matrix", payload)

    def test_agent_6_rag_query_targets_negative_signals(self):
        query = rag_runtime.AGENT_RAG_QUERIES[6]
        self.assertIn("downgrade", query)
        self.assertIn("下修", query)
        self.assertIn("warning", query)

    def test_agent_15_rag_query_targets_chip_and_sentiment(self):
        query = rag_runtime.AGENT_RAG_QUERIES[15]
        self.assertIn("institutional", query)
        self.assertIn("籌碼", query)
        self.assertIn("河流圖", query)

    def test_prompt_builder_supports_jinja_and_legacy_placeholders(self):
        rendered = prompt_builder.render_prompt_template(
            "標的 {ticker} {{ name }}{% if data.dividend_yield_raw > 0.05 %} DDM{% endif %}",
            {
                "ticker": "2330.TW",
                "name": "台積電",
                "data": {"dividend_yield_raw": 0.06},
            },
        )
        self.assertEqual(rendered, "標的 2330.TW 台積電 DDM")

    def test_model_routing_policy(self):
        configured_agents = {
            int(agent_num): model
            for agent_num, model in config.MODEL_ROUTES.get("agents", {}).items()
        }
        for agent_num in [*range(1, 7), 17, 18]:
            expected = configured_agents.get(agent_num, config.DEFAULT_ANALYSIS_MODEL)
            expected_sequence = list(dict.fromkeys([expected, *config.AGENT_FALLBACK_MODELS.get(agent_num, [])]))
            self.assertEqual(ar.AGENT_MODELS[agent_num], expected)
            self.assertEqual(ar.get_agent_model_sequence(agent_num), expected_sequence)

        expected_decision = configured_agents.get(7, config.DEFAULT_DECISION_MODEL)
        expected_decision_sequence = list(dict.fromkeys([expected_decision, *config.AGENT_FALLBACK_MODELS.get(7, [])]))
        self.assertEqual(ar.AGENT_MODELS[7], expected_decision)
        self.assertEqual(ar.get_agent_model_sequence(7), expected_decision_sequence)
        expected_trading_decision = configured_agents.get(16, config.DEFAULT_DECISION_MODEL)
        expected_trading_decision_sequence = list(dict.fromkeys([expected_trading_decision, *config.AGENT_FALLBACK_MODELS.get(16, [])]))
        self.assertEqual(ar.AGENT_MODELS[16], expected_trading_decision)
        self.assertEqual(ar.get_agent_model_sequence(16), expected_trading_decision_sequence)
        expected_bubble_decision = configured_agents.get(19, config.DEFAULT_DECISION_MODEL)
        expected_bubble_decision_sequence = list(dict.fromkeys([expected_bubble_decision, *config.AGENT_FALLBACK_MODELS.get(19, [])]))
        self.assertEqual(ar.AGENT_MODELS[19], expected_bubble_decision)
        self.assertEqual(ar.get_agent_model_sequence(19), expected_bubble_decision_sequence)
        expected_audit_sequence = list(dict.fromkeys([config.AUDIT_MODEL, *config.AUDIT_FALLBACK_MODELS]))
        self.assertEqual(ar.get_audit_model_sequence(), expected_audit_sequence)
        self.assertGreaterEqual(len(ar.get_audit_model_sequence()), 2)
        self.assertTrue(config.AGENT_FALLBACK_MODELS.get(7))
        self.assertTrue(config.AGENT_FALLBACK_MODELS.get(15))
        self.assertTrue(config.AGENT_FALLBACK_MODELS.get(16))
        self.assertTrue(config.AGENT_FALLBACK_MODELS.get(19))
        self.assertEqual(ar.get_context_digest_model_sequence(), [config.CONTEXT_DIGEST_MODEL])

        context = {"_model_sequence_override": {2: ar.get_audit_model_sequence()}}
        self.assertEqual(ar.get_runtime_model_sequence(2, context), expected_audit_sequence)

    def test_peer_contamination_requires_explicit_peer_context(self):
        data = base_data()
        issues = ar.validate_company_identity(
            "大東電主要依賴大亞的儲能案場與太陽能工程收入。大亞同時是本公司核心成長來源。",
            data,
        )

        self.assert_has_issue(issues, "同業「大亞」在未標示為同業")

    def test_audit_reflection_tries_fallback_model_after_primary_quota_error(self):
        calls = []

        def fake_generate(api_key, model_id, prompt):
            calls.append(model_id)
            if model_id == "audit-primary":
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            return SimpleNamespace(text="fallback reflection")

        with patch.object(repair_reflection, "get_audit_model_sequence", return_value=["audit-primary", "audit-fallback"]):
            with patch.object(repair_reflection, "_generate_reflection_content", side_effect=fake_generate):
                reflection = repair_reflection.generate_audit_reflection(
                    2,
                    ["口徑紅線"],
                    "前次輸出",
                    {"ticker": "2330.TW", "company_name": "台積電"},
                    KeyRotator(["test-key"]),
                )

        self.assertEqual(calls, ["audit-primary", "audit-fallback"])
        self.assertEqual(reflection, "fallback reflection")

    def test_external_http_clients_parse_sync_and_async_payloads(self):
        old_fmp_key = edc.FMP_API_KEY
        old_google_key = edc.GOOGLE_SEARCH_API_KEY
        old_google_cse = edc.GOOGLE_CSE_ID
        edc.FMP_API_KEY = "test-fmp"
        edc.GOOGLE_SEARCH_API_KEY = "test-google"
        edc.GOOGLE_CSE_ID = "test-cse"

        def fake_sync_json_get(url, params):
            if "customsearch" in url:
                return {
                    "items": [{
                        "title": "法說會釋出展望",
                        "snippet": "營收與供應鏈展望",
                        "displayLink": "example.com",
                        "link": "https://example.test/news",
                        "pagemap": {"metatags": [{"article:published_time": "2026-06-04"}]},
                    }]
                }
            if "gdeltproject.org" in url:
                return {
                    "articles": [{
                        "title": "Alternative search headline",
                        "url": "https://example.test/search",
                        "domain": "example.test",
                        "seendate": "20260604T000000Z",
                    }]
                }
            if "news/stock" in url:
                return [{"title": "FMP headline", "date": "2026-06-04", "site": "FMP", "url": "https://example.test/fmp"}]
            return [{"price": 123.4, "marketCap": 1000}]

        async def fake_async_json_get(client, url, params, headers=None):
            return fake_sync_json_get(url, params)

        try:
            with patch.object(edc, "_sync_json_get", side_effect=fake_sync_json_get):
                quote = edc.fetch_fmp_quote_fallback("2330.TW")
                catalysts = edc.fetch_google_search_catalysts("2330.TW", "台積電", {"official_name": "台積電"})
                fmp_news = edc.fetch_fmp_news_catalysts("2330.TW")

            self.assertEqual(quote["price"], 123.4)
            self.assertEqual(catalysts[0]["source_type"], "google_search")
            self.assertEqual(fmp_news[0]["source_type"], "fmp_news")

            async def run_async_checks():
                with patch.object(edc, "_async_json_get", side_effect=fake_async_json_get), \
                        patch.object(edc._search, "WEB_SEARCH_PROVIDER_ORDER", "gdelt"):
                    quote_async = await edc.fetch_fmp_quote_fallback_async("2330.TW")
                    catalysts_async = await edc.fetch_google_search_catalysts_async("2330.TW", "台積電", {"official_name": "台積電"})
                    fmp_news_async = await edc.fetch_fmp_news_catalysts_async("2330.TW")
                    bundle = await edc.fetch_optional_http_data_bundle(
                        "2330.TW",
                        "台積電",
                        {"official_name": "台積電"},
                        sector="Technology",
                        industry="Semiconductor",
                        include_quote=True,
                    )
                return quote_async, catalysts_async, fmp_news_async, bundle

            quote_async, catalysts_async, fmp_news_async, bundle = asyncio.run(run_async_checks())
            self.assertEqual(quote_async["price"], 123.4)
            self.assertEqual(catalysts_async[0]["source_type"], "google_search")
            self.assertEqual(fmp_news_async[0]["title"], "FMP headline")
            self.assertEqual(bundle["fmp_quote"]["price"], 123.4)
            self.assertEqual(bundle["search_catalysts"][0]["source_type"], "gdelt_search")
            self.assertEqual(bundle["search_peer_discovery"][0]["source_type"], "alternative_peer_discovery")
            self.assertEqual(bundle["google_peer_discovery"][0]["source_type"], "google_peer_discovery")
        finally:
            edc.FMP_API_KEY = old_fmp_key
            edc.GOOGLE_SEARCH_API_KEY = old_google_key
            edc.GOOGLE_CSE_ID = old_google_cse

    def test_fmp_news_uses_stable_search_stock_news_endpoint(self):
        old_fmp_key = edc.FMP_API_KEY
        old_fmp_base_url = edc.FMP_BASE_URL
        edc.FMP_API_KEY = "test-fmp"
        edc.FMP_BASE_URL = "https://financialmodelingprep.com/stable"
        calls = []

        def fake_sync_json_get(url, params):
            calls.append((url, dict(params)))
            if url == "https://financialmodelingprep.com/stable/news/stock":
                return [{"title": "FMP headline", "date": "2026-06-04", "site": "FMP", "url": "https://example.test/fmp"}]
            return []

        try:
            with patch.object(edc, "_sync_json_get", side_effect=fake_sync_json_get):
                fmp_news = edc.fetch_fmp_news_catalysts("2330.tw")

            self.assertEqual(fmp_news[0]["title"], "FMP headline")
            self.assertEqual(calls, [(
                "https://financialmodelingprep.com/stable/news/stock",
                {"symbols": "2330.TW", "limit": 5, "apikey": "test-fmp"},
            )])
        finally:
            edc.FMP_API_KEY = old_fmp_key
            edc.FMP_BASE_URL = old_fmp_base_url

    def test_external_http_failures_emit_structured_warnings(self):
        warning = external_http_client.build_http_warning("FMP", "quote", RuntimeError("boom"))
        self.assertEqual(warning["type"], "external_http_warning")
        self.assertEqual(warning["provider"], "FMP")
        self.assertEqual(warning["operation"], "quote")
        self.assertEqual(warning["error_kind"], "RuntimeError")
        self.assertIn("boom", warning["message"])

        old_fmp_key = edc.FMP_API_KEY
        edc.FMP_API_KEY = "test-fmp"
        captured = []

        def capture_warning(provider, operation, exc):
            captured.append(external_http_client.build_http_warning(provider, operation, exc))
            return captured[-1]

        try:
            with patch.object(edc, "_sync_json_get", side_effect=RuntimeError("quote down")), \
                    patch.object(edc, "log_http_warning", side_effect=capture_warning):
                quote = edc.fetch_fmp_quote_fallback("2330.TW")

            self.assertEqual(quote, {})
            self.assertEqual(captured[0]["provider"], "FMP")
            self.assertEqual(captured[0]["operation"], "quote fallback")
            self.assertEqual(captured[0]["error_kind"], "RuntimeError")
            self.assertIn("quote down", captured[0]["message"])
        finally:
            edc.FMP_API_KEY = old_fmp_key

    def test_external_http_warning_redacts_api_keys_from_messages(self):
        request = httpx.Request(
            "GET",
            "https://financialmodelingprep.com/stable/news/stock?symbols=2330.TW&limit=5&apikey=secret-fmp-key",
        )
        response = httpx.Response(403, request=request)
        exc = httpx.HTTPStatusError(
            "Client error '403 Forbidden' for url "
            "'https://financialmodelingprep.com/stable/news/stock?symbols=2330.TW&limit=5&apikey=secret-fmp-key'",
            request=request,
            response=response,
        )

        warning = external_http_client.build_http_warning("FMP", "news", exc)

        self.assertNotIn("secret-fmp-key", warning["message"])
        self.assertIn("apikey=<redacted>", warning["message"])

    def test_optional_http_bundle_records_task_warnings(self):
        async def boom(*args, **kwargs):
            raise RuntimeError("google down")

        async def empty(*args, **kwargs):
            return []

        async def run_check():
            with patch.object(edc, "fetch_google_search_catalysts_async", boom), \
                    patch.object(edc, "fetch_fmp_news_catalysts_async", empty), \
                    patch.object(edc, "fetch_google_peer_discovery_results_async", empty):
                return await edc.fetch_optional_http_data_bundle(
                    "2330.TW",
                    "台積電",
                    {"official_name": "台積電"},
                    sector="Technology",
                    industry="Semiconductor",
                )

        bundle = asyncio.run(run_check())

        self.assertEqual(bundle["google_catalysts"], [])
        self.assertEqual(bundle["_warnings"][0]["provider"], "optional_http_bundle")
        self.assertEqual(bundle["_warnings"][0]["operation"], "google_catalysts")
        self.assertEqual(bundle["_warnings"][0]["error_kind"], "RuntimeError")

    def test_async_stock_fetch_merges_optional_http_bundle(self):
        def fake_fetch_stock_data(ticker, skip_optional_http=False):
            self.assertEqual(ticker, "2330")
            self.assertTrue(skip_optional_http)
            return {
                "ticker": "2330.TW",
                "company_name": "台積電 / Taiwan Semiconductor",
                "company_identity": {
                    "official_name": "台積電",
                    "legal_name": "台灣積體電路製造股份有限公司",
                },
                "sector": "Technology",
                "industry": "Semiconductor",
                "recent_catalysts": [{"title": "Yahoo headline", "source_type": "yfinance_news"}],
                "peer_discovery_results": [],
                "data_source_notes": [],
            }

        calls = {}

        async def fake_google_catalysts(ticker, company_name, identity):
            calls["google"] = (ticker, company_name, identity)
            return [{"title": "Google headline", "source_type": "google_search"}]

        async def fake_peer_discovery(ticker, company_name, sector, industry):
            calls["peer"] = (ticker, company_name, sector, industry)
            return [{"title": "Peer result", "source_type": "google_peer_discovery"}]

        async def fake_fmp_news(ticker):
            calls.setdefault("fmp", []).append(ticker)
            if ticker == "2330":
                return []
            return [{"title": "FMP headline", "source_type": "fmp_news"}]

        async def empty_search(*args):
            return []

        with patch.object(financial_data, "fetch_stock_data", side_effect=fake_fetch_stock_data), \
                patch.object(optional_enrichment, "fetch_alternative_search_catalysts_async", side_effect=empty_search), \
                patch.object(optional_enrichment, "fetch_alternative_peer_discovery_async", side_effect=empty_search), \
                patch.object(optional_enrichment, "fetch_google_search_catalysts_async", side_effect=fake_google_catalysts), \
                patch.object(optional_enrichment, "fetch_google_peer_discovery_results_async", side_effect=fake_peer_discovery), \
                patch.object(optional_enrichment, "fetch_fmp_news_catalysts_async", side_effect=fake_fmp_news), \
                patch.object(cache_helpers, "set_cache_json") as cache_mock:
            data = asyncio.run(financial_data.async_fetch_stock_data("2330"))

        titles = [item["title"] for item in data["recent_catalysts"]]
        self.assertIn("Yahoo headline", titles)
        self.assertIn("Google headline", titles)
        self.assertIn("FMP headline", titles)
        self.assertEqual(data["peer_discovery_results"][0]["source_type"], "google_peer_discovery")
        self.assertEqual(calls["google"][0], "2330.TW")
        self.assertEqual(calls["google"][1], "台積電 / Taiwan Semiconductor")
        self.assertEqual(calls["google"][2]["official_name"], "台積電")
        self.assertEqual(calls["peer"], ("2330.TW", "台積電 / Taiwan Semiconductor", "Technology", "Semiconductor"))
        self.assertEqual(calls["fmp"], ["2330", "2330.TW"])
        self.assertTrue(cache_mock.called)

    def test_cyclical_low_pe_redline(self):
        data = {
            "company_name": "測試航運",
            "industry": "航運",
            "sector": "運輸",
            "pe_ratio_raw": 3.8,
        }
        issues = ar.validate_analysis_output(
            4,
            "本益比偏低，估值便宜，因此可判斷被低估並上修買入。",
            data,
        )
        self.assert_has_issue(issues, "景氣循環股紅線")

        clean = ar.validate_analysis_output(
            4,
            "本益比偏低，但航運屬景氣循環股，需先判斷是否處於獲利高峰與循環反轉風險。",
            data,
        )
        self.assertNotIn("景氣循環股紅線", "\n".join(clean))

    def test_pe_river_and_tear_sheet_render(self):
        context = complete_context()
        context["data"].update({
            "industry": "航運",
            "recent_catalysts": [{"title": "法說會釋出保守展望"}],
            "institutional_trading": {
                "trend": "accumulation",
                "total_net_buy_thousand_shares": 1234.5,
            },
            "pe_river_chart": {
                "years": ["2023", "2024", "2025"],
                "eps_twd": [5, 8, 10],
                "multiples": [8, 10, 12, 15],
                "bands": {
                    "8x": [40, 64, 80],
                    "10x": [50, 80, 100],
                    "12x": [60, 96, 120],
                    "15x": [75, 120, 150],
                },
                "source": "test",
            },
        })
        html = report_gen.generate_html_report(context)
        self.assertIn("One-Page Tear Sheet", html)
        self.assertIn("peRiverChart", html)
        self.assertIn("P/E 河流圖", html)
        self.assertIn("P/E 河流圖（EPS × 歷史本益比通道）", html)

    def test_chart_money_series_are_converted_from_billion_to_yi_twd(self):
        context = complete_context()
        context["data"].update({
            "years": ["2024", "2025"],
            "revenue_history": [5.53, 5.37],
            "net_income_history": [1.31, 1.49],
            "fcf_history": [0.70, 1.43],
            "gross_margin_history": [49.2, 54.2],
            "op_margin_history": [25.9, 30.0],
            "net_margin_history": [23.7, 27.7],
            "roe_history": [52.8, 22.9],
            "pe_river_chart": {"source": "default multiples"},
        })

        html = report_gen.generate_html_report(context)
        payload_text = html.split("const CHART_DATA = ", 1)[1].split(";\n", 1)[0]
        chart_data = json.loads(payload_text)

        self.assertEqual(chart_data["sourceMoneyUnit"], "billion_twd")
        self.assertEqual(chart_data["moneyUnit"], "hundred_million_twd")
        self.assertEqual(chart_data["revenue"], [55.3, 53.7])
        self.assertEqual(chart_data["netIncome"], [13.1, 14.9])
        self.assertEqual(chart_data["fcf"], [7.0, 14.3])
        self.assertIn("年度營收與淨利（億元台幣）", html)
        self.assertIn("P/E 河流圖（EPS × 預設本益比通道）", html)

    def test_tear_sheet_prompt_leak_falls_back_to_deterministic_summary(self):
        context = complete_context()
        context["tear_sheet_summary"] = (
            "Taiwan Stock Research Report Editor.\n"
            "Compress a full research report into a one-page practical summary.\n"
            "Investment recommendation, target price, fundamental highlights.\n"
            "No title, no Markdown. Just one single paragraph of summary text."
        )

        summary = report_gen.build_tear_sheet_summary(context)

        self.assertNotIn("Taiwan Stock Research Report Editor", summary)
        self.assertNotIn("Compress a full research report", summary)
        self.assertIn("一頁式摘要", summary)

    def test_pe_river_default_calculation(self):
        chart = financial_data.build_pe_river_chart_data(
            "TEST",
            ["2024", "2025"],
            [1, 2],
            100_000_000,
        )
        self.assertEqual(chart["eps_twd"], [10.0, 20.0])
        self.assertEqual(chart["bands"]["10x"], [100.0, 200.0])


if __name__ == "__main__":
    unittest.main()
