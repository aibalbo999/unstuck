import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import agent_runner as ar  # noqa: E402
import report_gen  # noqa: E402


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


class AuditRuleTests(unittest.TestCase):
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
            ar.validate_company_identity("大亞（1623.TW）是能源鏈整合服務商。大亞具備儲能業務。", base_data()),
            "公司身分錯置",
        )

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
            ctx["structured_outputs"][7] = {
                "recommendation": {
                    "建議": "避免",
                    "短期目標（3個月）": "NT$2500",
                    "中期目標（6個月）": "NT$2300",
                    "長期目標（12個月）": "NT$2150",
                    "長期潛力（5年）": "NT$3500",
                    "信心指數": "8/10",
                }
            }
            return (
                "## 最終投資決策\n"
                "建議避免。杜邦分析僅引用同期間年度杜邦恒等式，"
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


if __name__ == "__main__":
    unittest.main()
