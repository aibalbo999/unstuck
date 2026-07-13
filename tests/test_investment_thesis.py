def test_build_investment_thesis_creates_decision_discipline_payload():
    from investment_thesis import build_investment_thesis

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh", "summary": "核心資料新鮮"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(8)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
            "recent_catalysts": [{"title": "AI demand stays strong"}],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "短期目標（3個月）": "NT$980",
                "中期目標（6個月）": "NT$1050",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "price_targets": {"熊市情境": 800, "基本情境": 1050, "牛市情境": 1250},
            "moat_scores": {"整體護城河": 8.5, "成本優勢": 9.0},
        },
        "final_audit": {"warnings": ["高信心需揭露資料限制"], "critical": []},
        "analyses": {
            1: "商業模式清楚，先進製程與客戶黏著形成護城河。",
            2: "自由現金流穩健，資本支出仍需追蹤。",
        },
    }

    thesis = build_investment_thesis(context)

    assert thesis["ticker"] == "2330.TW"
    assert thesis["recommendation"] == "買入"
    assert thesis["information_richness"]["grade"] == "A"
    assert thesis["mirror_test"]["status"] == "pass"
    assert len(thesis["mirror_test"]["lines"]) == 5
    assert len(thesis["core_assumptions"]) >= 3
    assert any("護城河" in item["assumption"] for item in thesis["core_assumptions"])
    assert len(thesis["red_lines"]) >= 3
    assert thesis["health_score"] == 8
    assert thesis["next_review"]["trigger"] == "下一次季報或重大法說會後"


def test_build_investment_thesis_marks_sparse_low_trust_reports_as_gray_zone():
    from investment_thesis import build_investment_thesis

    context = {
        "ticker": "NEWCO",
        "company_name": "資料稀缺公司",
        "data": {
            "data_trust": {"status": "partial"},
            "source_audit": [{"source": "market_data", "status": "success"}],
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "長期目標（12個月）": "N/A",
                "信心指數": "7/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": ["資料缺口"], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["information_richness"]["grade"] == "C"
    assert thesis["mirror_test"]["status"] == "gray_zone"
    assert thesis["health_score"] <= 5
    assert any("資料不足" in gap for gap in thesis["data_gaps"])


def test_build_investment_thesis_preserves_final_audit_warnings_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessWarnings(list):
        def __bool__(self):
            raise KeyError("final audit warnings truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"}],
            "recent_catalysts": [{"title": "AI demand stays strong"}],
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "長期目標（12個月）": "NT$1000",
                "信心指數": "6/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {
            "warnings": BrokenTruthinessWarnings(["有效稽核提醒"]),
            "critical": [],
        },
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert "有效稽核提醒" in thesis["data_gaps"]


def test_build_investment_thesis_preserves_source_audit_count_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessSourceAudit(list):
        def __bool__(self):
            raise KeyError("source audit list truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": BrokenTruthinessSourceAudit([
                {"source": "market_data", "status": "success"},
                {"source": "financial_statements", "status": "success"},
                {"source": "recent_catalysts", "status": "success"},
                {"source": "institutional_trading", "status": "success"},
                {"source": "pe_river_chart", "status": "success"},
            ]),
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["information_richness"]["source_audit_count"] == 5
    assert thesis["information_richness"]["grade"] == "A"


def test_build_investment_thesis_preserves_history_series_count_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessHistoryList(list):
        def __bool__(self):
            raise KeyError("history list truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [
                {"source": "market_data", "status": "success"},
                {"source": "financial_statements", "status": "success"},
                {"source": "recent_catalysts", "status": "success"},
                {"source": "institutional_trading", "status": "success"},
                {"source": "pe_river_chart", "status": "success"},
            ],
            "revenue_history": BrokenTruthinessHistoryList([2200, 2600, 3100]),
            "net_income_history": BrokenTruthinessHistoryList([900, 1000, 1200]),
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["information_richness"]["history_series_count"] == 2
    assert thesis["information_richness"]["grade"] == "A"


def test_investment_thesis_markdown_preserves_list_fields_when_truthiness_fails():
    from investment_thesis import investment_thesis_markdown

    class BrokenTruthinessList(list):
        def __bool__(self):
            raise KeyError("markdown list truthiness unavailable")

    markdown = investment_thesis_markdown({
        "pipeline_id": "v1",
        "discipline_heading": "長線投資論文與決策紀律",
        "health_label": "論文健康度",
        "health_score": 8,
        "information_richness": {"grade": "A", "summary": "資料充足"},
        "mirror_test": {
            "status": "pass",
            "lines": BrokenTruthinessList(["鏡子測試仍有效"]),
        },
        "mirror_heading": "鏡子測試五句話",
        "assumptions_heading": "核心假設",
        "core_assumptions": BrokenTruthinessList([
            {
                "assumption": "核心營收不惡化",
                "validation": "追蹤季營收",
                "frequency": "每季",
            }
        ]),
        "red_lines_heading": "紅線",
        "red_lines": BrokenTruthinessList([
            {
                "severity": "嚴重",
                "condition": "自由現金流惡化",
                "action": "重跑完整報告",
            }
        ]),
        "data_gaps": BrokenTruthinessList(["需要補官方資料"]),
        "next_review": {
            "trigger": "下一次季報",
            "focus": "確認營收與現金流",
        },
    })

    assert "鏡子測試仍有效" in markdown
    assert "核心營收不惡化" in markdown
    assert "自由現金流惡化" in markdown
    assert "需要補官方資料" in markdown


def test_investment_thesis_markdown_collapses_embedded_newlines_in_display_fields():
    from investment_thesis import investment_thesis_markdown

    markdown = investment_thesis_markdown({
        "pipeline_id": "v1",
        "discipline_heading": "長線投資論文\n與決策紀律",
        "health_label": "論文\n健康度",
        "health_score": "8\n高",
        "information_richness": {"grade": "A\n級", "summary": "資料\n充足"},
        "mirror_test": {
            "status": "pass\n已確認",
            "lines": ["鏡子測試\n仍有效"],
        },
        "mirror_heading": "鏡子測試\n五句話",
        "assumptions_heading": "核心\n假設",
        "core_assumptions": [
            {
                "assumption": "核心營收\n不惡化",
                "validation": "追蹤\n季營收",
                "frequency": "每季\n一次",
            }
        ],
        "red_lines_heading": "風控\n紅線",
        "red_lines": [
            {
                "severity": "嚴重\n警示",
                "condition": "自由現金流\n惡化",
                "action": "重跑\n完整報告",
            }
        ],
        "data_gaps": ["需要補\n官方資料"],
        "next_review": {
            "trigger": "下一次\n季報",
            "focus": "確認營收\n與現金流",
        },
    })

    assert "## 長線投資論文 與決策紀律" in markdown
    assert "- **論文 健康度:** 8 高/10" in markdown
    assert "- **資訊豐富度:** A 級（資料 充足）" in markdown
    assert "- **鏡子測試:** pass 已確認" in markdown
    assert "### 鏡子測試 五句話" in markdown
    assert "- 鏡子測試 仍有效" in markdown
    assert "- **核心營收 不惡化**：追蹤 季營收（每季 一次）" in markdown
    assert "- **嚴重 警示**：自由現金流 惡化 -> 重跑 完整報告" in markdown
    assert "- 需要補 官方資料" in markdown
    assert "**下次檢查:** 下一次 季報；重點：確認營收 與現金流" in markdown
    assert "論文\n健康度" not in markdown
    assert "核心營收\n不惡化" not in markdown
    assert "需要補\n官方資料" not in markdown


def test_build_investment_thesis_preserves_recommendation_mapping_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessRecommendation(dict):
        def __bool__(self):
            raise KeyError("recommendation truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": BrokenTruthinessRecommendation({
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            }),
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["recommendation"] == "買入"
    assert thesis["valuation_anchor"]["target_12m"] == "NT$1200"
    assert thesis["health_score"] == 8


def test_build_investment_thesis_preserves_trade_setup_mapping_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessTradeSetup(dict):
        def __bool__(self):
            raise KeyError("trade setup truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v4",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "trade_setup": BrokenTruthinessTradeSetup({
                "trade_direction": "Long",
                "entry_zone": "NT$930-950",
                "target_price": "NT$1000",
                "stop_loss": "NT$900",
                "core_catalyst": "法說會上修展望",
                "risk_level": "Low",
            }),
            "recommendation": {},
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["recommendation"] == "偏多 Long"
    assert thesis["valuation_anchor"]["base_case"] == "NT$1000"
    assert any("NT$930-950" in line for line in thesis["mirror_test"]["lines"])


def test_build_investment_thesis_preserves_structured_triggers_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessTriggers(list):
        def __bool__(self):
            raise KeyError("scenario trigger truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v3",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "避免",
                "長期目標（12個月）": "NT$800",
                "信心指數": "7/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "structured_outputs": {
            24: {
                "scenario_triggers": BrokenTruthinessTriggers([
                    {
                        "direction": "bearish_downgrade",
                        "trigger_condition": "跌破月線",
                        "action": "建立避險",
                    },
                    {
                        "direction": "neutral_review",
                        "trigger_condition": "站回前高",
                        "action": "回補檢討",
                    },
                ])
            }
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert any("跌破月線：建立避險" in line for line in thesis["mirror_test"]["lines"])
    assert any("站回前高：回補檢討" in line for line in thesis["mirror_test"]["lines"])


def test_build_investment_thesis_preserves_data_trust_status_when_comparison_fails():
    from investment_thesis import build_investment_thesis

    class BrokenComparisonStatus:
        def __str__(self):
            return "partial"

        def __eq__(self, other):
            raise KeyError("data trust status comparison unavailable")

        def __hash__(self):
            raise KeyError("data trust status hash unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": BrokenComparisonStatus()},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert any("資料可信度狀態為 partial" in gap for gap in thesis["data_gaps"])
    assert any("partial data trust" in item["condition"] for item in thesis["red_lines"])


def test_build_investment_thesis_preserves_final_audit_critical_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessCritical(list):
        def __bool__(self):
            raise KeyError("final audit critical truthiness unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {
            "warnings": [],
            "critical": BrokenTruthinessCritical(["重大財報品質疑慮"]),
        },
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert any("重大財報品質疑慮" in line for line in thesis["mirror_test"]["lines"])


def test_build_investment_thesis_preserves_agent_analysis_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessAnalysis:
        def __bool__(self):
            raise KeyError("analysis text truthiness unavailable")

        def __str__(self):
            return "泡沫敘事仍未被現金流支持。第二句不應進入摘要。"

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v3",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "放空",
                "短期目標（3個月）": "NT$800",
                "中期目標（6個月）": "NT$760",
                "長期目標（12個月）": "NT$700",
                "信心指數": "7/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {
            17: BrokenTruthinessAnalysis(),
            18: "自由現金流品質正在惡化。",
        },
    }

    thesis = build_investment_thesis(context)

    assert any("泡沫假設：泡沫敘事仍未被現金流支持" in line for line in thesis["mirror_test"]["lines"])


def test_build_investment_thesis_preserves_current_price_fmt_when_truthiness_fails():
    from investment_thesis import build_investment_thesis

    class BrokenTruthinessPrice:
        def __bool__(self):
            raise KeyError("current price truthiness unavailable")

        def __str__(self):
            return "NT$950"

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": BrokenTruthinessPrice(),
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert thesis["valuation_anchor"]["current_price"] == "NT$950"
    assert any("我以 NT$950 評估" in line for line in thesis["mirror_test"]["lines"])


def test_build_investment_thesis_falls_back_when_moat_score_string_conversion_fails():
    from investment_thesis import build_investment_thesis

    class BrokenStringMoatScore:
        def __str__(self):
            raise KeyError("moat score string conversion unavailable")

    context = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": {
            "ticker": "2330.TW",
            "company_name": "台積電",
            "current_price": 950,
            "current_price_fmt": "NT$950",
            "data_trust": {"status": "fresh"},
            "source_audit": [{"source": "market_data", "status": "success"} for _ in range(5)],
            "revenue_history": [2200, 2600, 3100],
            "net_income_history": [900, 1000, 1200],
        },
        "parsed": {
            "recommendation": {
                "建議": "買入",
                "長期目標（12個月）": "NT$1200",
                "信心指數": "8/10",
            },
            "moat_scores": {"整體護城河": BrokenStringMoatScore()},
            "price_targets": {},
        },
        "final_audit": {"warnings": [], "critical": []},
        "analyses": {},
    }

    thesis = build_investment_thesis(context)

    assert any("護城河資料不足" in line for line in thesis["mirror_test"]["lines"])
