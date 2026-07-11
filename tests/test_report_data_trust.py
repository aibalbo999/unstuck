import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.legacy_report_gen as report_gen  # noqa: E402
from data_trust import build_data_snapshot  # noqa: E402
from reporting.evidence import build_key_evidence_rows  # noqa: E402
from reporting.execution_summary import build_execution_summary_html, build_execution_summary_markdown  # noqa: E402


class BrokenExecutionSummaryGateGet(dict):
    def get(self, key, default=None):
        if key in {"status", "verdict", "summary"}:
            raise RuntimeError("execution summary gate get unavailable")
        return dict.get(self, key, default)


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
    context["prompt_version"] = "runtime-rules:test"
    context["model_id"] = "gemini-test-model"
    context["code_commit"] = "abc123"
    context["code_dirty"] = True
    context["agent_sequence"] = [1, 2, 3]
    context["final_audit"] = {"status": "passed", "critical": [], "warnings": ["高信心需揭露資料限制"], "corrections": []}
    context["evidence_exit_gate"] = {
        "verdict": "caution",
        "summary": "部分抽樣數字無法對上資料快照，需人工確認。",
        "sampled_count": 3,
        "failed_count": 1,
    }
    context["report_conformance"] = {
        "status": "warning",
        "summary": "報告符合輸出契約，但仍需人工注意警示。",
    }

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)

    assert "本報告資料可信度" in html
    assert "報告使用範圍與判讀限制" in html
    assert "品質 gate 有警示" in html
    assert "資料信心分數" in html
    assert "可重現資訊" in html
    assert "gemini-test-model" in html
    assert "程式碼狀態：abc123（含未提交變更）" in html
    assert "資料新鮮" in html
    assert "關鍵數據來源對照" in html
    assert "股價與市值" in html
    assert "來源審計" in html
    assert "yfinance" in html
    assert "執行邏輯與模型檢查" in html
    assert "Pipeline V1" in html
    assert "Agent 執行序列" in html
    assert "Final audit：passed" in html
    assert "Evidence gate：caution" in html
    assert "Report conformance：warning" in html
    assert "## 本報告資料可信度" in markdown
    assert "## 報告使用範圍與判讀限制" in markdown
    assert "品質 gate 有警示" in markdown
    assert "**資料信心分數:**" in markdown
    assert "**可重現資訊:**" in markdown
    assert "runtime-rules:test" in markdown
    assert "程式碼狀態：abc123（含未提交變更）" in markdown
    assert "## 關鍵數據來源對照" in markdown
    assert "## 來源審計" in markdown
    assert "## 執行邏輯與模型檢查" in markdown
    assert "**Pipeline:** V1" in markdown
    assert "**Agent 執行序列:** Agent 1 → Agent 2 → Agent 3" in markdown
    assert "**Final audit:** passed" in markdown
    assert "**Evidence gate:** caution" in markdown
    assert "**Report conformance:** warning" in markdown
    assert "| 股價與市值 | 市場資料 | yfinance | 成功 |" in markdown
    assert "| 市場資料 | yfinance | 成功 |" in markdown


def test_execution_summary_keeps_quality_gate_mappings_when_accessor_fails():
    context = minimal_context()
    context["final_audit"] = BrokenExecutionSummaryGateGet({"status": "warning"})
    context["evidence_exit_gate"] = BrokenExecutionSummaryGateGet({
        "verdict": "caution",
        "summary": "部分抽樣數字需人工確認。",
    })
    context["report_conformance"] = BrokenExecutionSummaryGateGet({
        "status": "warning",
        "summary": "報告符合主要輸出契約，但仍需人工注意警示。",
    })
    context["report_lint"] = BrokenExecutionSummaryGateGet({"status": "warning"})

    markdown = build_execution_summary_markdown(context)
    html = build_execution_summary_html(context)

    assert "**Final audit:** warning" in markdown
    assert "**Evidence gate:** caution" in markdown
    assert "**Report conformance:** warning" in markdown
    assert "**Report lint:** warning" in markdown
    assert "部分抽樣數字需人工確認。" in markdown
    assert "報告符合主要輸出契約" in markdown
    assert "Final audit：warning" in html
    assert "Evidence gate：caution" in html
    assert "Report conformance：warning" in html
    assert "Report lint：warning" in html
    assert "部分抽樣數字需人工確認。" in html


def test_key_evidence_prefers_successful_provider_over_later_empty_provider():
    data = minimal_context()["data"]
    data["recent_catalysts"] = [{"title": "Alternative catalyst"}]
    data["source_audit"] = [
        {
            "source": "recent_catalysts",
            "provider": "Alternative Search",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
        {
            "source": "recent_catalysts",
            "provider": "FMP news",
            "status": "unavailable",
            "fetched_at": "2026-06-07T00:00:01+00:00",
            "record_count": 0,
            "cache_hit": False,
            "stale": False,
        },
    ]

    rows = build_key_evidence_rows(data)
    catalyst_row = next(row for row in rows if row["label"] == "近期催化劑")

    assert catalyst_row["status"] == "success"
    assert catalyst_row["provider"] == "Alternative Search"
    assert catalyst_row["record_count"] == 1


def test_key_evidence_includes_global_market_and_international_news_context():
    data = minimal_context()["data"]
    data["global_market_context"] = {
        "items": [{"symbol": "QQQ", "change_5d_pct": 2.4, "source": "yfinance"}],
    }
    data["international_news_context"] = {
        "topics": [{"tag": "macro", "headline": "Fed path drives risk appetite", "source": "GDELT"}],
    }
    data["source_audit"].extend([
        {
            "source": "global_market_context",
            "provider": "yfinance global context",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:00+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
        {
            "source": "international_news_context",
            "provider": "GDELT",
            "status": "success",
            "fetched_at": "2026-06-07T00:00:01+00:00",
            "record_count": 1,
            "cache_hit": False,
            "stale": False,
        },
    ])

    rows = build_key_evidence_rows(data)

    assert any(row["label"] == "全球市場脈絡" and row["provider"] == "yfinance global context" for row in rows)
    assert any(row["label"] == "國際新聞脈絡" and row["provider"] == "GDELT" for row in rows)


def test_report_artifacts_include_evidence_matrix_for_key_conclusions():
    context = minimal_context()
    context["parsed"]["price_targets"] = {
        "熊市情境": 80,
        "基本情境": 100,
        "牛市情境": 120,
    }
    context["parsed"]["moat_scores"] = {
        "品牌力": 8,
        "規模經濟": 9,
        "轉換成本": 7,
        "整體護城河": 8,
    }
    context["data"]["global_market_context"] = {"items": [{"symbol": "QQQ", "change_5d_pct": 2.4}]}
    context["data"]["international_news_context"] = {"topics": [{"tag": "macro", "headline": "Fed path"}]}
    context["data"]["source_audit"].extend([
        {"source": "global_market_context", "provider": "yfinance global context", "status": "success", "record_count": 1, "stale": False},
        {"source": "international_news_context", "provider": "GDELT", "status": "success", "record_count": 1, "stale": False},
    ])
    context["data"]["data_source_notes"] = ["TTM 淨利率已依最新財報補值。"]

    html = report_gen.generate_html_report(context)
    markdown = report_gen.generate_markdown_report(context)
    snapshot = build_data_snapshot(context, pipeline_id="v1")

    assert "報告證據矩陣" in html
    assert "估值結論" in html
    assert "TTM 淨利率已依最新財報補值。" in html
    assert "## 報告證據矩陣" in markdown
    assert "| 估值結論 |" in markdown
    assert "| 最終投資建議 |" in markdown
    assert snapshot["evidence_matrix"][0]["claim"] == "估值結論"
    assert any(row["claim"] == "最終投資建議" for row in snapshot["evidence_matrix"])
    assert any(
        row["claim"] == "最終投資建議" and "全球市場脈絡" in row["source"] and "國際新聞脈絡" in row["source"]
        for row in snapshot["evidence_matrix"]
    )
    assert any("TTM 淨利率已依最新財報補值。" in row["limitation"] for row in snapshot["evidence_matrix"])
