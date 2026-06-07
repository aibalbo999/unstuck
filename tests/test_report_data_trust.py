import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.legacy_report_gen as report_gen  # noqa: E402


def minimal_context():
    data = {
        "data_schema_version": 4,
        "ticker": "2330.TW",
        "company_name": "台積電",
        "sector": "Technology",
        "industry": "Semiconductors",
        "fetch_date": "2026年06月07日",
        "current_price": 100.0,
        "current_price_fmt": "NT$100.00",
        "market_cap_fmt": "NT$100億",
        "pe_ratio": "20.0x",
        "pb_ratio": "5.00x",
        "gross_margin": "50.0%",
        "roe": "20.0%",
        "dividend_yield": "2.00%",
        "beta": "1.00",
        "years": ["2024", "2025"],
        "revenue_history": [10, 12],
        "net_income_history": [2, 3],
        "fcf_history": [1, 2],
        "gross_margin_history": [50, 52],
        "op_margin_history": [30, 31],
        "net_margin_history": [20, 25],
        "roe_history": [18, 20],
        "price_history": {"dates": [], "prices": []},
        "source_freshness": {
            "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
            "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
        },
        "source_audit": [
            {
                "source": "market_data",
                "provider": "yfinance",
                "status": "success",
                "fetched_at": "2026-06-07T00:00:00+00:00",
                "duration_ms": 12,
                "record_count": 4,
                "cache_hit": False,
                "stale": False,
                "error_kind": "",
                "message": "ok",
            }
        ],
        "data_trust": {
            "status": "fresh",
            "critical_failures": [],
            "stale_sources": [],
            "last_market_data_at": "2026-06-07T00:00:00+00:00",
            "notes": ["測試資料新鮮。"],
        },
    }
    return {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "pipeline_id": "v1",
        "data": data,
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$100",
                "6個月": "NT$110",
                "12個月": "NT$120",
                "信心": "7/10",
            },
            "price_targets": {},
            "moat_scores": {},
        },
        "analyses": {},
        "final_audit": {"critical": [], "warnings": [], "corrections": []},
    }


def test_html_and_markdown_include_data_trust_and_source_audit():
    context = minimal_context()

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)

    assert "資料可信度" in html
    assert "資料新鮮" in html
    assert "來源審計" in html
    assert "yfinance" in html
    assert "## 資料可信度" in markdown
    assert "## 來源審計" in markdown
    assert "| 市場資料 | yfinance | 成功 |" in markdown
