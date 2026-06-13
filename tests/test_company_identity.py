import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_fetch.market_sources import identity  # noqa: E402
import reporting.legacy_report_gen as report_gen  # noqa: E402


def test_tpex_ticker_keeps_numeric_stock_id_for_company_identity(monkeypatch):
    monkeypatch.setattr(
        identity,
        "load_taiwan_stock_info_records",
        lambda: [
            {
                "stock_id": "3324",
                "stock_name": "雙鴻",
                "industry_category": "其他電子類",
                "type": "tpex",
            }
        ],
    )

    result = identity.build_company_identity("3324.TWO", {}, "Auras Technology Co., Ltd.")

    assert result["stock_id"] == "3324"
    assert result["official_name"] == "雙鴻"
    assert result["display_name"] == "雙鴻 / Auras Technology Co., Ltd."
    assert "雙鴻" in result["allowed_aliases"]


def test_report_renderers_prefer_company_identity_display_name():
    context = {
        "ticker": "3324.TWO",
        "company_name": "Auras Technology Co., Ltd.",
        "pipeline_id": "v1",
        "data": {
            "ticker": "3324.TWO",
            "company_name": "Auras Technology Co., Ltd.",
            "company_identity": {
                "official_name": "雙鴻",
                "display_name": "雙鴻 / Auras Technology Co., Ltd.",
            },
            "fetch_date": "2026年06月11日",
            "source_freshness": {},
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        },
        "parsed": {
            "recommendation": {"建議": "持有", "3個月": "NT$100", "6個月": "NT$110", "12個月": "NT$120", "信心": "6/10"},
            "price_targets": {"熊市情境": 80, "基本情境": 100, "牛市情境": 120},
            "moat_scores": {},
        },
        "analyses": {},
        "final_audit": {"critical": [], "warnings": [], "corrections": []},
    }

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)

    assert '<div class="sidebar-name">雙鴻 / Auras Technology Co., Ltd.</div>' in html
    assert "# 3324.TWO 雙鴻 / Auras Technology Co., Ltd." in markdown
    assert "一頁式摘要：3324.TWO 雙鴻 / Auras Technology Co., Ltd." in markdown
