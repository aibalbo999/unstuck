import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import agent_runner as ar  # noqa: E402
import financial_data  # noqa: E402
import financial_tools  # noqa: E402
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
            self.assertIn("前次退件反思摘要", ctx.get("_audit_reflection_instruction", ""))
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
                "建議持有。杜邦分析僅引用同期間年度杜邦恒等式；"
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

    def test_previous_context_is_not_truncated(self):
        long_agent_1 = "## 商業模式\n" + ("完整內容A" * 260)
        long_agent_2 = "## 財務分析\n" + ("完整內容B" * 260)
        context = {
            "analyses": {1: long_agent_1, 2: long_agent_2},
            "context_digests": {4: '{"decision_relevant_facts":["摘要"]}'},
        }

        formatted = ar._format_previous(context, 4)

        self.assertIn("【提煉 Agent 結構化摘要】", formatted)
        self.assertIn("完整內容A" * 20, formatted)
        self.assertIn("完整內容B" * 20, formatted)
        self.assertNotIn("完整內容A" * 80 + "...", formatted)

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

    def test_agent_function_tools_are_registered(self):
        self.assertEqual([tool.__name__ for tool in ar.get_agent_function_tools(2)], ["calculate_cagr"])
        self.assertEqual(
            [tool.__name__ for tool in ar.get_agent_function_tools(4)],
            ["calculate_cagr", "calculate_wacc", "calculate_dcf", "calculate_ddm"],
        )

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
