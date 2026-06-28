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
