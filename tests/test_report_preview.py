import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402
import api_report_service  # noqa: E402
import job_store  # noqa: E402
import report_index  # noqa: E402
import report_history_service  # noqa: E402
import report_rerun_rendering  # noqa: E402
import report_rerun_service  # noqa: E402
from data_fetch import FetchResult  # noqa: E402
from data_trust_snapshot import build_data_snapshot, verify_data_snapshot_integrity  # noqa: E402
from reporting import ReportBundle  # noqa: E402
from reporting.html_renderer import generate_html_report  # noqa: E402
from report_persistence import report_bundle_keys_for_filename  # noqa: E402
from report_paths import report_storage_prefix_for_filename  # noqa: E402
from report_repository import ReportListQuery  # noqa: E402


def list_reports_for_test(output_dir: Path, **overrides):
    params = {
        "page": 1,
        "limit": 20,
        "q": "",
        "pipeline": "all",
        "recommendation": "all",
        "data_trust": "all",
        "output_dir": str(output_dir),
        "report_cache": {},
    }
    params.update(overrides)
    return report_history_service.list_reports(**params)


def test_parse_recommendation_summary_from_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    (tmp_path / "2449_v2_report_20260606_010000.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "2449_v2_report_20260606_010000.md").write_text(
        """# 2449.TW 京元電子 - 實戰交易決策報告

## 一頁式摘要
京元電子目前建議採取「持有」策略，等待回檔後再分批布局。

## 📊 關鍵指標
- **股價:** NT$309.50

---

## 🎯 最終投資建議
- **綜合建議:** 持有
- **3個月目標:** NT$273
- **6個月目標:** NT$310
- **12個月目標:** NT$350
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )

    summary = report_history_service.parse_recommendation_summary(
        "2449_v2_report_20260606_010000.html",
        output_dir=str(tmp_path),
    )

    assert summary["recommendation"] == "持有"
    assert summary["current_price"] == "NT$309.50"
    assert summary["target_3m"] == "NT$273"
    assert summary["target_6m"] == "NT$310"
    assert summary["target_12m"] == "NT$350"
    assert summary["confidence"] == "7/10"
    assert "等待回檔" in summary["summary"]


def test_parse_recommendation_summary_from_partitioned_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_TW_v2_report_20260630_090000.html"
    report_dir = tmp_path / report_storage_prefix_for_filename(filename)
    report_dir.mkdir(parents=True)
    write_report_pair(report_dir, filename, "持有")

    summary = report_history_service.parse_recommendation_summary(filename, output_dir=str(tmp_path))

    assert summary["recommendation"] == "持有"
    assert summary["current_price"] == "NT$309.50"
    assert summary["target_12m"] == "NT$350"


def test_mode_c_report_preview_uses_bubble_sniper_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v3_report_20260606_010000.html"
    (tmp_path / filename).write_text(
        '<div class="sidebar-name">京元電子 / King Yuan Electronics Co., Ltd.</div>',
        encoding="utf-8",
    )
    (tmp_path / filename.replace(".html", ".md")).write_text(
        """# 2449.TW 京元電子 - 泡沫狙擊研究報告

## 一頁式摘要
泡沫題材已明顯脫離財務現實，應等待催化劑確認後採取空方或避開策略。

## 做空觸發條件（Catalyst for crash）
- 財測下修或法人連續賣超擴大，將觸發估值均值回歸。

## 防軋空停損點（Stop-loss level）
- 若股價放量突破前高且毛利率同步改善，應停止空方假設。

[投資建議]
建議：強烈放空
短期目標（3個月）：NT$220
中期目標（6個月）：NT$190
長期目標（12個月）：NT$160
長期潛力（5年）：需重新驗證
信心指數：8/10
[/投資建議]
""",
        encoding="utf-8",
    )

    result = list_reports_for_test(tmp_path, pipeline="v3", include_versions=True)

    preview = result["reports"][0]["preview"]
    assert preview["kind"] == "bubble_sniper"
    assert preview["title"] == "2449 泡沫狙擊預覽"
    assert preview["primary"] == {"label": "空方判斷", "value": "放空", "tone": "is-short"}
    assert [item["label"] for item in preview["metrics"]] == ["當日股價", "信心"]
    assert [item["label"] for item in preview["targets"]] == ["做空觸發", "防軋空停損", "3個月壓力"]
    assert "財測下修" in preview["targets"][0]["value"]
    assert "放量突破前高" in preview["targets"][1]["value"]
    assert "脫離財務現實" in preview["summary"]


def test_mode_d_report_preview_uses_trade_setup_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v4_report_20260606_010000.html"
    (tmp_path / filename).write_text(
        '<div class="sidebar-name">京元電子 / King Yuan Electronics Co., Ltd.</div>',
        encoding="utf-8",
    )
    (tmp_path / filename.replace(".html", ".md")).write_text(
        """# 2449.TW 京元電子 - 極短線交易策略報告

## 一頁式摘要
短線動能轉強，但需嚴守停損。
""",
        encoding="utf-8",
    )
    snapshot = {
        "ticker": "2449.TW",
        "pipeline": "v4",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
        "rerun_context": {
            "parsed": {
                "trade_setup": {
                    "trade_direction": "Long",
                    "entry_zone": "NT$300-305",
                    "target_price": "NT$330",
                    "stop_loss": "跌破 NT$292",
                    "core_catalyst": "外資回補與突破月線",
                    "risk_level": "Medium",
                }
            }
        },
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 309.5,
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
            "source_audit": [],
        },
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    result = list_reports_for_test(tmp_path, pipeline="v4", include_versions=True)

    preview = result["reports"][0]["preview"]
    assert preview["kind"] == "swing_trade"
    assert preview["title"] == "2449.TW 極短線交易預覽"
    assert preview["primary"] == {"label": "交易方向", "value": "偏多 Long", "tone": "is-long"}
    assert [item["label"] for item in preview["metrics"]] == ["當日股價", "風險"]
    assert [item["label"] for item in preview["targets"]] == ["進場區間", "1-2週目標", "停損"]
    assert preview["targets"][0]["value"] == "NT$300-305"
    assert preview["targets"][1]["value"] == "NT$330"
    assert preview["targets"][2]["value"] == "跌破 NT$292"
    assert preview["summary"] == "外資回補與突破月線"


def test_mode_d_report_preview_reads_partitioned_trade_setup_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "6282_TW_v4_report_20260627_195101.html"
    report_dir = tmp_path / "2026-06" / "6282.TW"
    report_dir.mkdir(parents=True)
    (report_dir / filename).write_text(
        '<div class="sidebar-name">康舒 / AcBel Polytech Inc.</div>',
        encoding="utf-8",
    )
    (report_dir / filename.replace(".html", ".md")).write_text(
        """# 6282.TW 康舒 - 極短線交易策略報告

## 一頁式摘要
短線中性觀望，等待支撐止跌。
""",
        encoding="utf-8",
    )
    snapshot = {
        "ticker": "6282.TW",
        "pipeline": "v4",
        "rerun_context": {
            "parsed": {
                "trade_setup": {
                    "trade_direction": "Neutral",
                    "entry_zone": "47.35 - 50.0 TWD",
                    "target_price": "59.9 TWD",
                    "stop_loss": "有效跌破 47.35 TWD",
                    "core_catalyst": "HVDC 放量驗證",
                    "risk_level": "High",
                }
            }
        },
        "data": {"ticker": "6282.TW", "company_name": "康舒", "current_price": 54.1},
    }
    (report_dir / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    result = list_reports_for_test(tmp_path, q="6282", pipeline="v4", include_versions=True)

    preview = result["reports"][0]["preview"]
    assert preview["targets"][0]["value"] == "47.35 - 50.0 TWD"
    assert preview["targets"][1]["value"] == "59.9 TWD"
    assert preview["targets"][2]["value"] == "有效跌破 47.35 TWD"
    assert preview["summary"] == "HVDC 放量驗證"


def test_mode_d_report_preview_falls_back_to_markdown_trade_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v4_report_20260606_010000.html"
    (tmp_path / filename).write_text(
        '<div class="sidebar-name">京元電子 / King Yuan Electronics Co., Ltd.</div>',
        encoding="utf-8",
    )
    (tmp_path / filename.replace(".html", ".md")).write_text(
        """# 2449.TW 京元電子 - 極短線交易策略報告

## 一頁式摘要
短線動能轉強，但需嚴守停損。

## 極短線交易計畫
- **交易方向:** Long
- **進場區間:** NT$300-305
- **1-2週目標:** NT$330
- **嚴格停損:** 跌破 NT$292
- **核心催化劑:** 外資回補與突破月線
- **短期波動風險:** Medium
""",
        encoding="utf-8",
    )
    snapshot = {
        "ticker": "2449.TW",
        "pipeline": "v4",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
        "rerun_context": {"parsed": {}},
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 309.5,
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
            "source_audit": [],
        },
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    result = list_reports_for_test(tmp_path, pipeline="v4", include_versions=True)

    preview = result["reports"][0]["preview"]
    assert preview["primary"] == {"label": "交易方向", "value": "偏多 Long", "tone": "is-long"}
    assert preview["targets"][0]["value"] == "NT$300-305"
    assert preview["targets"][1]["value"] == "NT$330"
    assert preview["targets"][2]["value"] == "跌破 NT$292"
    assert preview["summary"] == "外資回補與突破月線"
    assert preview["metrics"][1]["value"] == "Medium"


def test_rendered_report_surfaces_catalysts_with_watchlist_buttons():
    html = generate_html_report({
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline_id": "v2",
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 309.5,
            "current_price_fmt": "NT$309.50",
            "source_audit": [],
        },
        "analyses": {16: "## 最終風險總結\n等待下一季法說。"},
        "structured_outputs": {
            16: {
                "next_catalysts": [
                    {
                        "event_name": "Q3 法說會",
                        "expected_timeframe": "Q3 2026",
                        "impact_direction": "bullish",
                        "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
                    }
                ]
            }
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$300",
                "6個月": "NT$330",
                "12個月": "NT$350",
                "信心": "7/10",
            },
        },
    })

    assert "Key Catalysts to Watch" in html
    assert 'class="add-to-watchlist-btn"' in html
    assert 'data-ticker="2449.TW"' in html
    assert 'data-impact-direction="bullish"' in html
    assert 'data-trigger-desc="若管理層調升毛利率指引，重新評估上行情境。"' in html


def test_rendered_report_surfaces_catalysts_from_mapping_safe_structured_output_child_maps():
    from types import MappingProxyType

    html = generate_html_report({
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline_id": "v2",
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 309.5,
            "current_price_fmt": "NT$309.50",
            "source_audit": [],
        },
        "analyses": {16: "## 最終風險總結\n等待下一季法說。"},
        "structured_outputs": {
            16: MappingProxyType(
                {
                    "next_catalysts": [
                        {
                            "event_name": "Q3 法說會",
                            "expected_timeframe": "Q3 2026",
                            "impact_direction": "bullish",
                            "trigger_condition": "若管理層調升毛利率指引，重新評估上行情境。",
                        }
                    ]
                }
            )
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$300",
                "6個月": "NT$330",
                "12個月": "NT$350",
                "信心": "7/10",
            },
        },
    })

    assert "Key Catalysts to Watch" in html
    assert 'class="add-to-watchlist-btn"' in html
    assert 'data-trigger-desc="若管理層調升毛利率指引，重新評估上行情境。"' in html


def test_rendered_report_catalyst_plain_text_ignores_truthiness_failures():
    class BrokenPlainTextTruthiness:
        def __bool__(self):
            raise KeyError("report plain text truthiness unavailable")

        def __str__(self):
            return "若管理層調升毛利率指引，重新評估上行情境。"

    html = generate_html_report({
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline_id": "v2",
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 309.5,
            "current_price_fmt": "NT$309.50",
            "source_audit": [],
        },
        "analyses": {16: "## 最終風險總結\n等待下一季法說。"},
        "structured_outputs": {
            16: {
                "next_catalysts": [
                    {
                        "event_name": "Q3 法說會",
                        "expected_timeframe": "Q3 2026",
                        "impact_direction": "bullish",
                        "trigger_condition": BrokenPlainTextTruthiness(),
                    }
                ]
            }
        },
        "parsed": {
            "recommendation": {
                "建議": "持有",
                "3個月": "NT$300",
                "6個月": "NT$330",
                "12個月": "NT$350",
                "信心": "7/10",
            },
        },
    })

    assert "Key Catalysts to Watch" in html
    assert 'data-trigger-desc="若管理層調升毛利率指引，重新評估上行情境。"' in html


def write_report_pair(output_dir: Path, filename: str, recommendation: str):
    (output_dir / filename).write_text(
        '<div class="sidebar-name">京元電子 / King Yuan Electronics Co., Ltd.</div>',
        encoding="utf-8",
    )
    (output_dir / filename.replace(".html", ".md")).write_text(
        f"""# 2449.TW 京元電子 - 報告

## 一頁式摘要
測試摘要。

## 📊 關鍵指標
- **股價:** NT$309.50

---

## 🎯 最終投資建議
- **綜合建議:** {recommendation}
- **3個月目標:** NT$273
- **6個月目標:** NT$310
- **12個月目標:** NT$350
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )


def write_data_snapshot(output_dir: Path, filename: str, status: str = "fresh", current_price: float = 309.5):
    (output_dir / filename.replace(".html", ".data.json")).write_text(
        f"""{{
  "ticker": "2449.TW",
  "pipeline": "v2",
  "data_trust": {{
    "status": "{status}",
    "critical_failures": [],
    "stale_sources": [],
    "last_market_data_at": "2026-06-06T01:00:00+00:00",
    "notes": ["測試資料可信度"]
  }},
  "source_audit": []
  ,
  "data": {{
    "data_schema_version": 4,
    "ticker": "2449.TW",
    "company_name": "京元電子",
    "current_price": {current_price},
    "data_trust": {{
      "status": "{status}",
      "critical_failures": [],
      "stale_sources": [],
      "last_market_data_at": "2026-06-06T01:00:00+00:00",
      "notes": ["測試資料可信度"]
    }},
    "source_freshness": {{}},
    "source_audit": []
  }}
}}""",
        encoding="utf-8",
    )


def test_get_reports_filters_pipeline_and_recommendation(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")
    write_data_snapshot(tmp_path, "2449_v2_report_20260606_010000.html", "fresh")
    write_report_pair(tmp_path, "2449_report_20260606_005900.html", "買入")

    result = list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")

    assert result["pagination"]["pipeline"] == "v2"
    assert result["pagination"]["recommendation"] == "持有"
    assert result["pagination"]["total"] == 1
    assert result["reports"][0]["filename"] == "2449_v2_report_20260606_010000.html"
    assert result["reports"][0]["recommendation"]["current_price"] == "NT$309.50"
    tracking = result["reports"][0]["decision_tracking"]
    assert tracking["status"] == "tracked"
    assert tracking["initial_price"] == 309.5
    assert tracking["latest_price"] == 309.5
    assert tracking["target_12m"] == 350.0
    assert tracking["return_pct"] == 0.0
    freshness = result["reports"][0]["decision_freshness"]
    assert freshness["status"] == "current"
    assert freshness["requires_rerun"] is False
    assert result["reports"][0]["data_trust"]["status"] == "fresh"


def test_get_reports_normalizes_legacy_stored_recommendation_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v3_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "強烈放空")
    write_data_snapshot(tmp_path, filename, "fresh")
    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    legacy_recommendation = {
        "recommendation": "強烈放空",
        "current_price": "NT$309.50",
        "target_3m": "NT$273",
        "target_6m": "NT$310",
        "target_12m": "NT$350",
        "confidence": "7/10",
        "summary": "測試摘要。",
    }
    with report_index._connect() as conn:
        conn.execute(
            """
            UPDATE reports
            SET recommendation_json = ?, normalized_recommendation = '強烈放空', decision_tracking_json = '{}'
            WHERE filename = ?
            """,
            (json.dumps(legacy_recommendation, ensure_ascii=False), filename),
        )

    result = list_reports_for_test(tmp_path, pipeline="v3", recommendation="放空")

    assert result["pagination"]["total"] == 1
    report = result["reports"][0]
    assert report["recommendation"]["recommendation"] == "放空"
    assert report["decision_tracking"]["recommendation"] == "放空"
    assert report["preview"]["primary"]["value"] == "放空"


def test_get_reports_recovers_company_name_from_snapshot_when_index_has_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")
    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    with report_index._connect() as conn:
        conn.execute("UPDATE reports SET company_name = ticker WHERE filename = ?", (filename,))

    reports, _ = report_index.query_report_metadata(
        page=1,
        limit=10,
        output_dir=str(tmp_path),
        sync_metadata=False,
    )

    assert reports[0]["ticker"] == "2449.TW"
    assert reports[0]["company_name"] == "京元電子"


def test_report_index_uses_snapshot_ticker_for_legacy_unsuffixed_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "3131_v3_report_20260701_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    snapshot = {
        "ticker": "3131.TWO",
        "pipeline": "v3",
        "generated_at": "2026-07-01T01:00:00+00:00",
        "data_trust": {
            "status": "fresh",
            "critical_failures": [],
            "stale_sources": [],
            "notes": [],
        },
        "source_audit": [],
        "data": {
            "data_schema_version": 4,
            "ticker": "3131.TWO",
            "company_name": "弘塑",
            "current_price": 100,
            "source_freshness": {},
            "source_audit": [],
        },
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    reports, _ = report_index.query_report_metadata(
        page=1,
        limit=10,
        output_dir=str(tmp_path),
        sync_metadata=False,
    )

    assert reports[0]["ticker"] == "3131.TWO"
    with report_index._connect() as conn:
        row = conn.execute("SELECT search_text FROM reports WHERE filename = ?", (filename,)).fetchone()
    assert "3131.two" in row["search_text"]


def test_report_compare_api_returns_decision_and_tracking_deltas(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    left = "2449_v2_report_20260606_010000.html"
    right = "2449_v2_report_20260607_010000.html"
    write_report_pair(tmp_path, left, "持有")
    write_report_pair(tmp_path, right, "買入")
    write_data_snapshot(tmp_path, left, "stale", current_price=100)
    write_data_snapshot(tmp_path, right, "fresh", current_price=120)

    client = TestClient(api.app)
    response = client.get("/api/reports/compare", params={"left": left, "right": right})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["compatibility"]["same_ticker"] is True
    assert body["compatibility"]["same_pipeline"] is True
    assert body["compatibility"]["date_order"] == "chronological"
    assert body["compatibility"]["warnings"] == []
    assert body["diff"]["recommendation_changed"] is True
    assert body["diff"]["recommendation"] == {"before": "持有", "after": "買入"}
    assert body["diff"]["data_trust"]["score"]["delta"] is not None
    assert body["diff"]["tracking"]["latest_price"]["delta"] == 20


def test_report_compare_warns_when_compared_conclusion_needs_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    left = "2449_v2_report_20260606_010000.html"
    right = "2449_v2_report_20260607_010000.html"
    write_report_pair(tmp_path, left, "持有")
    write_report_pair(tmp_path, right, "持有")
    write_data_snapshot(tmp_path, left, "fresh", current_price=100)
    write_data_snapshot(tmp_path, right, "fresh", current_price=120)
    right_snapshot_path = tmp_path / right.replace(".html", ".data.json")
    right_snapshot = json.loads(right_snapshot_path.read_text(encoding="utf-8"))
    right_snapshot.update({
        "refreshed_without_analysis_rerun": True,
        "analysis_text_stale_message": "資料快照已刷新，但投資結論仍以原報告生成時間為準。",
        "decision_validity_status": "needs_rerun",
        "conclusion_generated_at": "2026-06-07T01:00:00+00:00",
        "snapshot_refreshed_at": "2026-06-08T01:00:00+00:00",
    })
    right_snapshot_path.write_text(json.dumps(right_snapshot, ensure_ascii=False), encoding="utf-8")

    client = TestClient(api.app)
    response = client.get("/api/reports/compare", params={"left": left, "right": right})

    assert response.status_code == 200
    body = response.json()
    warning_codes = {item["code"] for item in body["compatibility"]["warnings"]}
    assert "right_decision_needs_rerun" in warning_codes
    assert body["right"]["decision_freshness"]["status"] == "needs_rerun"
    assert body["diff"]["decision_freshness"] == {
        "status_before": "current",
        "status_after": "needs_rerun",
        "requires_rerun_before": False,
        "requires_rerun_after": True,
    }


def test_report_compare_api_warns_for_incompatible_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    left = "2449_v2_report_20260608_010000.html"
    right = "2308_report_20260607_010000.html"
    write_report_pair(tmp_path, left, "持有")
    write_report_pair(tmp_path, right, "買入")

    client = TestClient(api.app)
    response = client.get("/api/reports/compare", params={"left": left, "right": right})

    assert response.status_code == 200
    compatibility = response.json()["compatibility"]
    warning_codes = {item["code"] for item in compatibility["warnings"]}
    assert compatibility["same_ticker"] is False
    assert compatibility["same_pipeline"] is False
    assert compatibility["date_order"] == "reverse"
    assert compatibility["is_comparable"] is False
    assert {"different_ticker", "different_pipeline", "reverse_chronology"} <= warning_codes
    assert compatibility["suggested_order"] == {"left": right, "right": left}


def test_get_reports_marks_old_reports_without_snapshot_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")

    result = list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")

    assert result["reports"][0]["data_trust"]["status"] == "unknown"


def test_get_reports_marks_snapshot_hash_mismatch_as_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    snapshot = {
        "ticker": "2449.TW",
        "pipeline": "v2",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
        "source_audit": [],
        "data": {"ticker": "2449.TW", "current_price": 309.5},
        "snapshot_hash": "0" * 64,
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    result = list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")

    integrity = result["reports"][0]["snapshot_integrity"]
    assert integrity["status"] == "invalid"
    assert integrity["valid"] is False
    assert "snapshot_hash mismatch" in integrity["errors"]


def test_get_reports_rebuilds_empty_legacy_decision_tracking(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")
    with report_index._connect() as conn:
        conn.execute("UPDATE reports SET decision_tracking_json = '{}'")

    result = list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")

    tracking = result["reports"][0]["decision_tracking"]
    assert tracking["status"] == "tracked"
    assert tracking["latest_price"] == 309.5
    assert tracking["return_pct"] == 0.0


def test_get_reports_repairs_bad_recommendation_from_partitioned_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_TW_v2_report_20260630_090000.html"
    report_dir = tmp_path / report_storage_prefix_for_filename(filename)
    report_dir.mkdir(parents=True)
    write_report_pair(report_dir, filename, "持有")
    write_data_snapshot(report_dir, filename, "fresh", current_price=309.5)
    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    bad_recommendation = {
        "recommendation": "N/A",
        "current_price": "N/A",
        "target_3m": "N/A",
        "target_6m": "N/A",
        "target_12m": "N/A",
        "confidence": "N/A",
        "summary": "",
    }
    with report_index._connect() as conn:
        conn.execute(
            "UPDATE reports SET recommendation_json = ?, decision_tracking_json = '{}' WHERE filename = ?",
            (json.dumps(bad_recommendation, ensure_ascii=False), filename),
        )

    reports, _ = report_index.query_report_metadata(
        page=1,
        limit=10,
        q="2449",
        output_dir=str(tmp_path),
        sync_metadata=False,
    )

    recommendation = reports[0]["recommendation"]
    tracking = reports[0]["decision_tracking"]
    assert recommendation["recommendation"] == "持有"
    assert recommendation["target_12m"] == "NT$350"
    assert tracking["status"] == "tracked"
    assert tracking["initial_price"] == 309.5


def test_get_reports_reindexes_bad_partitioned_recommendation_before_filtering(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_TW_v2_report_20260630_090000.html"
    report_dir = tmp_path / report_storage_prefix_for_filename(filename)
    report_dir.mkdir(parents=True)
    write_report_pair(report_dir, filename, "持有")
    write_data_snapshot(report_dir, filename, "fresh", current_price=309.5)
    report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))
    bad_recommendation = {
        "recommendation": "N/A",
        "current_price": "N/A",
        "target_3m": "N/A",
        "target_6m": "N/A",
        "target_12m": "N/A",
        "confidence": "N/A",
        "summary": "",
    }
    with report_index._connect() as conn:
        conn.execute(
            """
            UPDATE reports
            SET recommendation_json = ?, normalized_recommendation = 'N/A', decision_tracking_json = '{}'
            WHERE filename = ?
            """,
            (json.dumps(bad_recommendation, ensure_ascii=False), filename),
        )

    result = list_reports_for_test(tmp_path, recommendation="持有")

    assert [report["filename"] for report in result["reports"]] == [filename]
    assert result["reports"][0]["recommendation"]["recommendation"] == "持有"


def test_report_history_uses_repository_boundary(tmp_path):
    class FakeRepository:
        def __init__(self):
            self.query_arg = None

        def query(self, query):
            self.query_arg = query
            return ([{"filename": "fake.html", "data_trust": {"status": "fresh"}}], 1)

    repository = FakeRepository()
    result = report_history_service.list_reports(
        page=2,
        limit=5,
        q="  2449  ",
        pipeline="mode_b",
        recommendation="持有",
        data_trust="fresh",
        include_versions=True,
        output_dir=str(tmp_path),
        report_cache={},
        repository=repository,
    )

    assert isinstance(repository.query_arg, ReportListQuery)
    assert repository.query_arg.pipeline == "v2"
    assert repository.query_arg.q == "2449"
    assert repository.query_arg.data_trust == "fresh"
    assert repository.query_arg.include_versions is True
    assert result["pagination"]["include_versions"] is True
    assert result["pagination"]["total"] == 1


def test_report_history_allows_callers_to_skip_metadata_sync(tmp_path):
    class FakeRepository:
        def __init__(self):
            self.query_arg = None

        def query(self, query):
            self.query_arg = query
            return ([], 0)

    repository = FakeRepository()

    report_history_service.list_reports(
        page=1,
        limit=5,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(tmp_path),
        report_cache={},
        repository=repository,
        sync_metadata=False,
    )

    assert repository.query_arg.sync_metadata is False


def test_report_history_returns_empty_payload_when_index_unavailable(tmp_path):
    class UnavailableRepository:
        def query(self, query):
            raise sqlite3.OperationalError("unable to open database file")

    result = report_history_service.list_reports(
        page=1,
        limit=8,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(tmp_path),
        report_cache={},
        repository=UnavailableRepository(),
    )

    assert result["reports"] == []
    assert result["pagination"]["total"] == 0
    assert result["pagination"]["total_pages"] == 1


def test_get_reports_defaults_to_latest_report_per_ticker_and_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filenames = [
        "2449_report_20260606_010000.html",
        "2449_report_20260606_020000.html",
        "2449_v2_report_20260606_010000.html",
        "2449_v2_report_20260606_020000.html",
    ]
    for filename in filenames:
        write_report_pair(tmp_path, filename, "持有")

    old_v1 = tmp_path / "2449_report_20260606_010000.html"
    old_v2 = tmp_path / "2449_v2_report_20260606_010000.html"
    future_mtime = 1_900_000_000
    os.utime(old_v1, (future_mtime, future_mtime))
    os.utime(old_v2, (future_mtime, future_mtime))

    result = list_reports_for_test(tmp_path)

    returned = {report["filename"] for report in result["reports"]}
    assert result["pagination"]["include_versions"] is False
    assert result["pagination"]["total"] == 2
    assert returned == {
        "2449_report_20260606_020000.html",
        "2449_v2_report_20260606_020000.html",
    }


def test_get_reports_treats_exchange_suffix_as_same_ticker_version(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filenames = [
        "2449_v1_report_20260606_010000.html",
        "2449_TW_v1_report_20260606_020000.html",
        "2449_v2_report_20260606_010000.html",
        "2449_TW_v2_report_20260606_020000.html",
    ]
    for filename in filenames:
        write_report_pair(tmp_path, filename, "持有")

    result = list_reports_for_test(tmp_path)

    assert result["pagination"]["include_versions"] is False
    assert result["pagination"]["total"] == 2
    assert {report["filename"] for report in result["reports"]} == {
        "2449_TW_v1_report_20260606_020000.html",
        "2449_TW_v2_report_20260606_020000.html",
    }


def test_get_reports_can_include_old_report_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filenames = [
        "2449_report_20260606_010000.html",
        "2449_report_20260606_020000.html",
        "2449_v2_report_20260606_010000.html",
        "2449_v2_report_20260606_020000.html",
    ]
    for filename in filenames:
        write_report_pair(tmp_path, filename, "持有")

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"limit": 20, "include_versions": "1"})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["include_versions"] is True
    assert body["pagination"]["total"] == 4
    assert {report["filename"] for report in body["reports"]} == set(filenames)


def test_get_reports_filters_data_trust_status(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    write_report_pair(tmp_path, "2449_v2_report_20260606_010000.html", "持有")
    write_data_snapshot(tmp_path, "2449_v2_report_20260606_010000.html", "stale")
    write_report_pair(tmp_path, "2330_v2_report_20260606_020000.html", "持有")
    write_data_snapshot(tmp_path, "2330_v2_report_20260606_020000.html", "fresh")

    client = TestClient(api.app)
    response = client.get("/api/reports", params={"data_trust": "stale", "pipeline": "v2", "limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["data_trust"] == "stale"
    assert body["pagination"]["total"] == 1
    assert body["reports"][0]["filename"] == "2449_v2_report_20260606_010000.html"
    assert body["reports"][0]["data_trust"]["status"] == "stale"


def test_download_data_snapshot_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "partial")

    client = TestClient(api.app)
    response = client.get(f"/api/report/{filename}/download/data")

    assert response.status_code == 200
    assert response.json()["data_trust"]["status"] == "partial"

    missing = client.get("/api/report/2449_v2_report_20260606_020000.html/download/data")
    assert missing.status_code == 404


def test_refresh_data_snapshot_endpoint_updates_trust(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "stale")
    refresh_options = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            refresh_options.append(request.options)
            return FetchResult(
                request=request,
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "京元電子",
                    "source_freshness": {
                        "market_data": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                        "financial_statements": {"stale": False, "fetched_at": "2026-06-07T00:00:00+00:00"},
                    },
                    "source_audit": [
                        {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1},
                        {"source": "financial_statements", "provider": "fake", "status": "success", "record_count": 1},
                    ],
                    "current_price": 330.0,
                    "data_trust": {
                        "status": "fresh",
                        "critical_failures": [],
                        "stale_sources": [],
                        "last_market_data_at": "2026-06-07T00:00:00+00:00",
                        "notes": ["刷新後資料新鮮"],
                    },
                },
            )

    monkeypatch.setattr(api, "get_data_refresh_service", lambda _app: FakeRefreshService())
    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/refresh/data", headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data_trust"]["status"] == "fresh"
    assert body["analysis_text_stale"] is True
    assert "分析本文" in body["analysis_text_stale_message"]
    assert body["decision_freshness"]["status"] == "needs_rerun"
    assert body["decision_freshness"]["requires_rerun"] is True
    assert body["decision_freshness"]["snapshot_refreshed_at"]
    assert "投資結論仍以原報告生成時間為準" in body["decision_freshness"]["requires_rerun_reason"]
    assert [item.force_refresh for item in refresh_options] == [True]
    assert [item.record_provider_sla for item in refresh_options] == [False]
    assert body["refresh_diff"]["data_trust_status"] == {"before": "stale", "after": "fresh", "changed": True}
    assert "可信度 stale → fresh" in body["refresh_diff"]["summary"]
    saved = json.loads((tmp_path / filename.replace(".html", ".data.json")).read_text(encoding="utf-8"))
    assert saved["data_trust"]["status"] == "fresh"
    assert saved["refreshed_from_report"] == filename
    assert saved["refreshed_without_analysis_rerun"] is True
    assert saved["decision_validity_status"] == "needs_rerun"
    assert saved["conclusion_generated_at"]
    assert saved["snapshot_refreshed_at"]

    reports = list_reports_for_test(tmp_path, pipeline="v2", recommendation="持有")
    assert reports["reports"][0]["analysis_text_stale"] is True
    assert "分析本文" in reports["reports"][0]["analysis_text_stale_message"]
    assert reports["reports"][0]["decision_freshness"]["status"] == "needs_rerun"
    assert reports["reports"][0]["decision_freshness"]["requires_rerun"] is True
    tracking = reports["reports"][0]["decision_tracking"]
    assert tracking["latest_price"] == 330.0
    assert tracking["return_pct"] == 6.6236
    assert tracking["target_12m_gap_pct"] == 6.0606
    assert tracking["refreshed_without_analysis_rerun"] is True


def test_refresh_data_snapshot_keeps_decision_current_when_only_provider_sla_changes(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh", current_price=309.5)

    class FakeRefreshService:
        async def fetch_async(self, request):
            return FetchResult(
                request=request,
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "京元電子",
                    "source_freshness": {
                        "market_data": {"stale": False, "fetched_at": "2026-06-06T01:00:00+00:00"},
                        "financial_statements": {"stale": False, "fetched_at": "2026-06-06T01:00:00+00:00"},
                    },
                    "source_audit": [
                        {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1},
                        {"source": "financial_statements", "provider": "fake", "status": "success", "record_count": 1},
                    ],
                    "current_price": 309.5,
                    "data_trust": {
                        "status": "partial",
                        "critical_failures": [],
                        "stale_sources": [],
                        "last_market_data_at": "2026-06-06T01:00:00+00:00",
                        "notes": ["來源健康度警示，但核心資料未變動。"],
                        "reason_codes": ["fresh_core_sources", "provider_sla_critical"],
                    },
                },
            )

    monkeypatch.setattr(api, "get_data_refresh_service", lambda _app: FakeRefreshService())
    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/refresh/data", headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_text_stale"] is False
    assert body["decision_freshness"]["status"] == "current"
    assert body["decision_freshness"]["requires_rerun"] is False
    saved = json.loads((tmp_path / filename.replace(".html", ".data.json")).read_text(encoding="utf-8"))
    assert saved["refreshed_without_analysis_rerun"] is False
    assert saved["decision_validity_status"] == "current"


def test_refresh_data_snapshot_endpoint_rejects_legacy_without_snapshot(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")

    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/refresh/data", headers=mutation_headers)

    assert response.status_code == 404


def test_rerun_report_endpoint_mode_b_queues_job(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    class FakeTaskQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

    fake_queue = FakeTaskQueue()
    monkeypatch.setattr(api, "analysis_task_queue", fake_queue)

    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["queued"] is True
    assert body["scope"] == "mode_b"
    assert body["filename"] == filename
    assert body["stream_url"].endswith(f"job_id={body['job_id']}")
    assert fake_queue.calls[0][0] == f"report-rerun:{body['job_id']}"
    assert fake_queue.calls[0][2:] == (body["job_id"], filename, "mode_b")
    job = job_store.get_job(body["job_id"])
    assert job["ticker"] == filename
    assert job["pipeline_id"] == "rerun:mode_b"


def test_rerun_report_endpoint_full_report_queues_job(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    class FakeTaskQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

    fake_queue = FakeTaskQueue()
    monkeypatch.setattr(api, "analysis_task_queue", fake_queue)

    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "full"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "full_report"
    assert "完整重跑" in body["scope_label"]
    assert fake_queue.calls[0][2:] == (body["job_id"], filename, "full_report")
    assert job_store.get_job(body["job_id"])["pipeline_id"] == "rerun:full_report"


def test_rerun_report_endpoint_attaches_existing_active_job(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    class FakeTaskQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

    fake_queue = FakeTaskQueue()
    monkeypatch.setattr(api, "analysis_task_queue", fake_queue)

    client = TestClient(api.app, raise_server_exceptions=False)
    first = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)
    second = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert len(fake_queue.calls) == 1


def test_rerun_report_endpoint_attached_malformed_status_does_not_error_or_requeue(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")
    attached_job_id = "attached-malformed-status"

    class BrokenStatus:
        def __bool__(self):
            raise RuntimeError("status truthiness failed")

        def __str__(self):
            raise RuntimeError("status string conversion failed")

    class FakeTaskQueue:
        def __init__(self):
            self.queue = self
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

        def fetch_job(self, _task_id):
            return None

    def fake_create_or_attach_active_job(ticker, pipeline_id, *, preserve_ticker_case=False):
        assert ticker == filename
        assert pipeline_id == "rerun:mode_b"
        assert preserve_ticker_case is True
        return {
            "job": {
                "job_id": attached_job_id,
                "ticker": filename,
                "pipeline_id": "rerun:mode_b",
                "status": BrokenStatus(),
            },
            "created": False,
            "cancelled_job_ids": [],
        }

    fake_queue = FakeTaskQueue()
    monkeypatch.setattr(api, "analysis_task_queue", fake_queue)
    monkeypatch.setattr(api, "create_or_attach_active_job", fake_create_or_attach_active_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["job_id"] == attached_job_id
    assert fake_queue.calls == []


def test_rerun_report_endpoint_attached_malformed_created_flag_does_not_error_or_requeue(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")
    attached_job_id = "attached-malformed-created"

    class BrokenCreatedFlag:
        def __bool__(self):
            raise RuntimeError("created flag truthiness failed")

    class FakeTaskQueue:
        def __init__(self):
            self.queue = self
            self.calls = []

        def enqueue(self, *args):
            self.calls.append(args)

        def fetch_job(self, _task_id):
            return None

    def fake_create_or_attach_active_job(ticker, pipeline_id, *, preserve_ticker_case=False):
        assert ticker == filename
        assert pipeline_id == "rerun:mode_b"
        assert preserve_ticker_case is True
        return {
            "job": {
                "job_id": attached_job_id,
                "ticker": filename,
                "pipeline_id": "rerun:mode_b",
                "status": "running",
            },
            "created": BrokenCreatedFlag(),
            "cancelled_job_ids": [],
        }

    fake_queue = FakeTaskQueue()
    monkeypatch.setattr(api, "analysis_task_queue", fake_queue)
    monkeypatch.setattr(api, "create_or_attach_active_job", fake_create_or_attach_active_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["job_id"] == attached_job_id
    assert fake_queue.calls == []


def test_rerun_report_endpoint_requeues_orphaned_active_job(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")
    orphan_job_id = job_store.create_job(filename, "rerun:mode_b")

    class InspectableQueue:
        def __init__(self):
            self.queue = self
            self.calls = []
            self.jobs = {}

        def enqueue(self, *args):
            self.calls.append(args)
            self.jobs[args[0]] = {"id": args[0], "status": "queued"}
            return self.jobs[args[0]]

        def fetch_job(self, task_id):
            return self.jobs.get(task_id)

    queue = InspectableQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "mode_b"}, headers=mutation_headers)

    assert response.status_code == 200
    assert response.json()["job_id"] == orphan_job_id
    assert queue.calls[0][0] == f"report-rerun:{orphan_job_id}"
    events = [event["payload"] for event in job_store.get_events_since(orphan_job_id)]
    assert any(event.get("phase") == "queue_recovered" for event in events)


def test_rerun_report_endpoint_queue_failure_event_preserves_source_filename(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    class FailingTaskQueue:
        def enqueue(self, *_args):
            raise RuntimeError("queue unavailable")

    monkeypatch.setattr(api, "analysis_task_queue", FailingTaskQueue())

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "full"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    job = job_store.get_job(body["job_id"])
    events = [event["payload"] for event in job_store.get_events_since(body["job_id"])]
    error_event = next(event for event in events if event["type"] == "error")

    assert job["status"] == "error"
    assert error_event["message"] == "報告重跑任務送入佇列失敗：queue unavailable"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_report_endpoint_queue_failure_uses_safe_message_fallback(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "fresh")

    class BrokenQueueError(Exception):
        def __str__(self):
            raise RuntimeError("queue exception string conversion failed")

    class FailingTaskQueue:
        def enqueue(self, *_args):
            raise BrokenQueueError()

    monkeypatch.setattr(api, "analysis_task_queue", FailingTaskQueue())

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun", params={"scope": "full"}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    job = job_store.get_job(body["job_id"])
    events = [event["payload"] for event in job_store.get_events_since(body["job_id"])]
    error_event = next(event for event in events if event["type"] == "error")

    assert job["status"] == "error"
    assert error_event["message"] == "報告重跑任務送入佇列失敗：未知錯誤"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_report_analysis_full_report_refreshes_data_before_pipeline(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    write_data_snapshot(tmp_path, filename, "stale", current_price=309.5)
    refresh_requests = []
    runner_requests = []
    progress_events = []

    class FakeRefreshService:
        async def fetch_async(self, request):
            refresh_requests.append(request)
            return FetchResult(
                request=request,
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "京元電子",
                    "current_price": 333.0,
                    "source_freshness": {"market_data": {"stale": False}},
                    "source_audit": [{"source": "market_data", "provider": "fake", "status": "success"}],
                    "data_trust": {
                        "status": "fresh",
                        "critical_failures": [],
                        "stale_sources": [],
                        "last_market_data_at": "2026-06-07T00:00:00+00:00",
                        "notes": ["完整重跑使用刷新資料"],
                    },
                },
            )

    class FakePipelineRunner:
        async def run_async(self, request):
            runner_requests.append(request)
            return SimpleNamespace(
                context={
                    "ticker": request.data["ticker"],
                    "company_name": request.data["company_name"],
                    "data": request.data,
                    "analyses": {11: "macro"},
                    "structured_outputs": {},
                    "start_time": 0,
                    "pipeline_id": request.pipeline_id,
                }
            )

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html='<div class="sidebar-name">京元電子</div>',
                markdown="# refreshed report",
                data_snapshot={
                    "snapshot_schema_version": 3,
                    "ticker": request.context["ticker"],
                    "company_name": request.context["company_name"],
                    "pipeline": request.pipeline_id,
                    "generated_at": "2026-06-07T00:00:00+00:00",
                    "data_schema_version": 4,
                    "source_freshness": request.context["data"].get("source_freshness", {}),
                    "source_audit": request.context["data"].get("source_audit", []),
                    "data_trust": request.context["data"]["data_trust"],
                    "rerun_context": {},
                    "data": request.context["data"],
                },
            )

    body = asyncio.run(
        report_rerun_service.rerun_report_analysis(
            filename,
            scope="full_report",
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=FakeReportRenderer(),
            refresh_service=FakeRefreshService(),
            progress_callback=progress_events.append,
        )
    )

    assert body["success"] is True
    assert body["scope"] == "full_report"
    assert body["data_trust"]["status"] == "fresh"
    assert [request.options.force_refresh for request in refresh_requests] == [True]
    assert runner_requests[0].pipeline_id == "v2"
    assert runner_requests[0].data["current_price"] == 333.0
    assert any(event.get("phase") == "rerun_refresh_data" for event in progress_events)


def test_full_report_rerun_accepts_mapping_safe_refreshed_data_payload(tmp_path, monkeypatch):
    from types import MappingProxyType, SimpleNamespace

    runner_requests = []

    async def fake_render_and_save_rerun_report(**kwargs):
        return {
            "success": True,
            "scope": kwargs["scope"],
            "data_trust": kwargs["context"]["data"]["data_trust"],
        }

    monkeypatch.setattr(report_rerun_service, "render_and_save_rerun_report", fake_render_and_save_rerun_report)

    class FakeRefreshService:
        async def fetch_async(self, request):
            return SimpleNamespace(
                data=MappingProxyType(
                    {
                        "data_schema_version": 4,
                        "ticker": request.ticker,
                        "company_name": "京元電子",
                        "current_price": 333.0,
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "fake",
                                    "status": "success",
                                }
                            ),
                        ),
                        "data_trust": MappingProxyType(
                            {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                        ),
                    }
                )
            )

    class FakePipelineRunner:
        async def run_async(self, request):
            runner_requests.append(request)
            return SimpleNamespace(
                context={
                    "ticker": request.data["ticker"],
                    "company_name": request.data["company_name"],
                    "data": request.data,
                    "analyses": {},
                    "structured_outputs": {},
                    "start_time": 0,
                    "pipeline_id": request.pipeline_id,
                }
            )

    body = asyncio.run(
        report_rerun_service._run_full_pipeline_rerun(
            snapshot={
                "ticker": "2449",
                "pipeline": "v2",
                "data": {"ticker": "2449", "company_name": "京元電子", "current_price": 309.5},
            },
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=object(),
            source_filename="2449_v2_report_20260606_010000.html",
            pipeline_id="v2",
            scope="full_report",
            refresh_service=FakeRefreshService(),
        )
    )

    assert body["success"] is True
    assert body["data_trust"]["status"] == "fresh"
    assert runner_requests[0].data["current_price"] == 333.0
    assert runner_requests[0].data["source_audit"][0]["status"] == "success"


def test_full_report_rerun_normalizes_mapping_safe_existing_snapshot_data(tmp_path, monkeypatch):
    from types import MappingProxyType, SimpleNamespace

    runner_requests = []

    async def fake_render_and_save_rerun_report(**kwargs):
        return {
            "success": True,
            "scope": kwargs["scope"],
            "source_audit": kwargs["context"]["data"]["source_audit"],
        }

    monkeypatch.setattr(report_rerun_service, "render_and_save_rerun_report", fake_render_and_save_rerun_report)

    class FakePipelineRunner:
        async def run_async(self, request):
            request.data["source_audit"].append({"source": "rerun", "provider": "pipeline", "status": "success"})
            runner_requests.append(request)
            return SimpleNamespace(
                context={
                    "ticker": request.data["ticker"],
                    "company_name": request.data["company_name"],
                    "data": request.data,
                    "analyses": {},
                    "structured_outputs": {},
                    "start_time": 0,
                    "pipeline_id": request.pipeline_id,
                }
            )

    body = asyncio.run(
        report_rerun_service._run_full_pipeline_rerun(
            snapshot={
                "ticker": "2449",
                "pipeline": "v2",
                "data": MappingProxyType(
                    {
                        "ticker": "2449",
                        "company_name": "京元電子",
                        "current_price": 309.5,
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "snapshot",
                                    "status": "success",
                                }
                            ),
                        ),
                        "data_trust": MappingProxyType(
                            {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                        ),
                    }
                ),
            },
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=object(),
            source_filename="2449_v2_report_20260606_010000.html",
            pipeline_id="v2",
            scope="full_report",
        )
    )

    assert body["success"] is True
    assert runner_requests[0].data["data_trust"]["status"] == "fresh"
    assert body["source_audit"][-1]["source"] == "rerun"


def test_rerun_report_persists_valid_snapshot_hash_after_metadata_added(tmp_path, monkeypatch):
    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    context = {
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline_id": "v2",
        "data": {
            "data_schema_version": 4,
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "current_price": 100.0,
            "source_freshness": {},
            "source_audit": [],
            "data_trust": {
                "status": "fresh",
                "critical_failures": [],
                "stale_sources": [],
                "last_market_data_at": "2026-06-07T00:00:00+00:00",
                "notes": [],
            },
        },
        "analyses": {},
        "structured_outputs": {},
    }

    class FakeReportRenderer:
        async def render_async(self, request):
            snapshot = build_data_snapshot(
                request.context,
                pipeline_id=request.pipeline_id,
                generated_at="2026-06-07T00:00:00+00:00",
            )
            assert verify_data_snapshot_integrity(snapshot)["valid"] is True
            return ReportBundle(
                html='<div class="sidebar-name">京元電子</div>',
                markdown="""# 2449.TW 京元電子 - 報告

## 一頁式摘要
測試摘要。

## 📊 關鍵指標
- **股價:** NT$100.00

---

## 🎯 最終投資建議
- **綜合建議:** 持有
- **3個月目標:** NT$90
- **6個月目標:** NT$110
- **12個月目標:** NT$120
- **信心指數:** 6/10
""",
                data_snapshot=snapshot,
            )

    body = asyncio.run(
        report_rerun_rendering.render_and_save_rerun_report(
            context=context,
            pipeline_id="v2",
            output_dir=str(tmp_path),
            report_renderer=FakeReportRenderer(),
            scope="full_report",
            source_filename="2449_v2_report_20260606_010000.html",
        )
    )
    stored_keys = report_bundle_keys_for_filename(body["filename"])
    stored = json.loads((tmp_path / stored_keys.data_key).read_text(encoding="utf-8"))

    assert stored["partial_rerun"]["source_report"] == "2449_v2_report_20260606_010000.html"
    assert stored["rerun_scope"] == "full_report"
    assert verify_data_snapshot_integrity(stored)["valid"] is True


def test_rerun_rendering_accepts_mapping_safe_renderer_snapshot(tmp_path, monkeypatch):
    from collections.abc import Mapping
    from types import MappingProxyType

    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))

    class ItemsOnlyMapping(Mapping):
        def __init__(self, data):
            self._data = data

        def __getitem__(self, key):
            return self._data[key]

        def __iter__(self):
            raise RuntimeError("direct iteration disabled")

        def __len__(self):
            return len(self._data)

        def items(self):
            return self._data.items()

    context = {
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline_id": "v2",
        "data": {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
        },
        "analyses": {},
        "structured_outputs": {},
    }

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html='<div class="sidebar-name">京元電子</div>',
                markdown="# 2449.TW 京元電子 - 報告\n",
                data_snapshot=ItemsOnlyMapping(
                    {
                        "snapshot_schema_version": 3,
                        "ticker": "2449.TW",
                        "company_name": "京元電子",
                        "pipeline": request.pipeline_id,
                        "generated_at": "2026-06-07T00:00:00+00:00",
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "snapshot",
                                    "status": "success",
                                }
                            ),
                        ),
                        "data_trust": MappingProxyType(
                            {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                        ),
                        "data": MappingProxyType({"ticker": "2449.TW", "company_name": "京元電子"}),
                    }
                ),
            )

    body = asyncio.run(
        report_rerun_rendering.render_and_save_rerun_report(
            context=context,
            pipeline_id="v2",
            output_dir=str(tmp_path),
            report_renderer=FakeReportRenderer(),
            scope="full_report",
            source_filename="2449_v2_report_20260606_010000.html",
        )
    )
    stored_keys = report_bundle_keys_for_filename(body["filename"])
    stored = json.loads((tmp_path / stored_keys.data_key).read_text(encoding="utf-8"))

    assert stored["source_audit"][0]["status"] == "success"
    assert stored["data_trust"]["status"] == "fresh"
    assert stored["partial_rerun"]["source_report"] == "2449_v2_report_20260606_010000.html"
    assert verify_data_snapshot_integrity(stored)["valid"] is True


def test_rerun_rendering_accepts_mapping_safe_context_payload(tmp_path, monkeypatch):
    from types import MappingProxyType

    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.db"))
    context = MappingProxyType(
        {
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "pipeline_id": "v2",
            "data": {
                "ticker": "2449.TW",
                "company_name": "京元電子",
                "source_audit": [],
                "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
            },
            "analyses": {},
            "structured_outputs": {},
        }
    )
    renderer_contexts = []

    class FakeReportRenderer:
        async def render_async(self, request):
            renderer_contexts.append(request.context)
            return ReportBundle(
                html='<div class="sidebar-name">京元電子</div>',
                markdown="# 2449.TW 京元電子 - 報告\n",
                data_snapshot={
                    "snapshot_schema_version": 3,
                    "ticker": request.context["ticker"],
                    "company_name": request.context["company_name"],
                    "pipeline": request.pipeline_id,
                    "generated_at": "2026-06-07T00:00:00+00:00",
                    "source_audit": [],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
                    "data": request.context["data"],
                },
            )

    body = asyncio.run(
        report_rerun_rendering.render_and_save_rerun_report(
            context=context,
            pipeline_id="v2",
            output_dir=str(tmp_path),
            report_renderer=FakeReportRenderer(),
            scope="full_report",
            source_filename="2449_v2_report_20260606_010000.html",
        )
    )
    stored_keys = report_bundle_keys_for_filename(body["filename"])
    stored = json.loads((tmp_path / stored_keys.data_key).read_text(encoding="utf-8"))

    assert renderer_contexts[0]["partial_rerun"]["scope"] == "full_report"
    assert body["partial_rerun"]["source_report"] == "2449_v2_report_20260606_010000.html"
    assert stored["partial_rerun"]["generated_report"] == body["filename"]
    assert verify_data_snapshot_integrity(stored)["valid"] is True


def test_rerun_report_stream_replays_terminal_event(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:final_recommendation")
    job_store.update_job(job_id, "done", filename="2449_v2_report_20260607_010000.html")
    job_store.append_event(job_id, {
        "type": "done",
        "filename": "2449_v2_report_20260607_010000.html",
        "rerun_scope": "final_recommendation",
        "source_filename": filename,
    })

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )

    assert response.status_code == 200
    assert '"type": "job"' in response.text
    assert '"type": "done"' in response.text
    assert "2449_v2_report_20260607_010000.html" in response.text


def test_rerun_report_stream_negative_last_event_id_header_falls_back_to_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:final_recommendation")
    job_store.update_job(job_id, "done", filename="2449_v2_report_20260607_010000.html")
    job_store.append_event(job_id, {
        "type": "done",
        "filename": "2449_v2_report_20260607_010000.html",
        "rerun_scope": "final_recommendation",
        "source_filename": filename,
    })

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id},
        headers={"Last-Event-ID": "-2"},
    )

    assert response.status_code == 200
    assert '"resume_after_id": 0' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_payload_uses_status_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:final_recommendation")
    job_store.update_job(job_id, "done", filename="2449_v2_report_20260607_010000.html")
    with sqlite3.connect(job_store.TASK_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO analysis_events (job_id, payload, created_at, event_type, phase, level)
            VALUES (?, ?, ?, 'event', '', '')
            """,
            (job_id, json.dumps(["malformed", "event"]), 1.0),
        )

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )

    assert response.status_code == 200
    assert '"type": "status"' in response.text
    assert "略過格式異常的報告重跑事件" in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_payload_type_uses_status_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-payload-type"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {"id": 1, "payload": {"type": memoryview(b"progress"), "message": "unsafe type"}},
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "status"' in response.text
    assert "略過格式異常的報告重跑事件" in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_container_payload_type_uses_status_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-container-payload-type"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": {"kind": "progress"},
                        "message": "不應信任容器 type",
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "status"' in response.text
    assert "略過格式異常的報告重跑事件" in response.text
    assert "不應信任容器 type" not in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_message_uses_safe_text_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-message"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {"id": 1, "payload": {"type": "progress", "message": memoryview(b"unsafe message")}},
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "progress"' in response.text
    assert '"message": ""' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_name_detail_use_safe_text_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-name-detail"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "message": "刷新資料中",
                        "name": memoryview(b"refresh data"),
                        "detail": memoryview(b"fetching market data"),
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "progress"' in response.text
    assert '"name": ""' in response.text
    assert '"detail": ""' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_control_fields_use_safe_text_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-control"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "phase": memoryview(b"rerun_refresh_data"),
                        "level": memoryview(b"info"),
                        "message": "刷新資料中",
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "progress"' in response.text
    assert '"phase": ""' in response.text
    assert '"level": ""' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_context_fields_use_safe_text_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-context"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "message": "刷新資料中",
                        "rerun_scope": memoryview(b"final_recommendation"),
                        "scope_label": memoryview(b"final recommendation"),
                        "pipeline_id": memoryview(b"rerun:final_recommendation"),
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "progress"' in response.text
    assert '"rerun_scope": ""' in response.text
    assert '"scope_label": ""' in response.text
    assert '"pipeline_id": ""' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_count_fields_use_integer_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-count"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "message": "刷新資料中",
                        "current": memoryview(b"1"),
                        "total": memoryview(b"2"),
                        "agent_num": memoryview(b"3"),
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "progress"' in response.text
    assert '"current": 0' in response.text
    assert '"total": 0' in response.text
    assert '"agent_num": 0' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_status_code_uses_integer_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-status-code"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "error",
            "error": "報告重跑失敗",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "error",
                        "message": "報告重跑失敗",
                        "status_code": memoryview(b"500"),
                    },
                }
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert '"status_code": 0' in response.text


def test_rerun_report_stream_malformed_replay_structured_fields_use_snapshot_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-structured"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "report_done",
                        "filename": "2449_v2_report_20260607_010000.html",
                        "data_trust": {"status": memoryview(b"fresh")},
                        "partial_rerun": {"scope": memoryview(b"final_recommendation")},
                        "metadata": {"pipeline_id": memoryview(b"rerun:final_recommendation")},
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "report_done"' in response.text
    assert '"data_trust": {"status": ""}' in response.text
    assert '"partial_rerun": {"scope": ""}' in response.text
    assert '"metadata": {"pipeline_id": ""}' in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_filename_uses_safe_text_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-filename"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "done",
                        "filename": memoryview(b"2449_v2_report_20260607_010000.html"),
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert '"filename": ""' in response.text


def test_rerun_report_stream_malformed_replay_event_row_uses_status_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-row"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                ["malformed", "event"],
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "status"' in response.text
    assert "略過格式異常的報告重跑事件" in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_replay_event_id_uses_integer_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-event-id"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    def fake_get_events_since(candidate_job_id, after_id):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": b"1",
                    "payload": {
                        "type": "progress",
                        "message": "不應信任二進位事件 id",
                    },
                },
                {
                    "id": 2,
                    "payload": {
                        "type": "done",
                        "filename": "2449_v2_report_20260607_010000.html",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "status"' in response.text
    assert "略過格式異常的報告重跑事件" in response.text
    assert "不應信任二進位事件 id" not in response.text
    assert '"type": "done"' in response.text


def test_rerun_report_stream_malformed_event_collection_uses_terminal_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-events"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", lambda *_args, **_kwargs: None)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "2449_v2_report_20260607_010000.html" in response.text


def test_rerun_report_stream_malformed_setup_job_row_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-setup"

    monkeypatch.setattr(api, "get_job", lambda candidate_job_id: ["malformed", candidate_job_id])

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 404
    assert "找不到報告重跑任務" in response.text


def test_rerun_report_stream_missing_job_after_setup_uses_error_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "missing-after-setup"
    calls = {"get_job": 0}

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        calls["get_job"] += 1
        if calls["get_job"] == 1:
            return {
                "job_id": job_id,
                "ticker": filename,
                "pipeline_id": "rerun:mode_b",
                "status": "running",
            }
        return None

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", lambda *_args, **_kwargs: [])

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "找不到報告重跑任務" in response.text
    assert '"rerun_scope": "mode_b"' in response.text
    assert filename in response.text


def test_rerun_report_stream_malformed_job_row_after_setup_uses_error_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "malformed-after-setup"
    calls = {"get_job": 0}

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        calls["get_job"] += 1
        if calls["get_job"] == 1:
            return {
                "job_id": job_id,
                "ticker": filename,
                "pipeline_id": "rerun:mode_b",
                "status": "running",
            }
        return ["malformed", candidate_job_id]

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", lambda *_args, **_kwargs: [])

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "找不到報告重跑任務" in response.text
    assert '"rerun_scope": "mode_b"' in response.text
    assert filename in response.text


def test_rerun_report_stream_missing_job_after_setup_persists_error_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")
    calls = {"get_job": 0}

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        calls["get_job"] += 1
        if calls["get_job"] == 1:
            return {
                "job_id": job_id,
                "ticker": filename,
                "pipeline_id": "rerun:mode_b",
                "status": "running",
            }
        return None

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next((event for event in events if event["type"] == "error"), None)

    assert response.status_code == 200
    assert "找不到報告重跑任務" in response.text
    assert error_event == {
        "type": "error",
        "message": "找不到報告重跑任務",
        "rerun_scope": "mode_b",
        "source_filename": filename,
    }


def test_rerun_report_stream_malformed_job_status_does_not_interrupt_polling(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "rerun-malformed-status"
    calls = {"get_job": 0}

    class BrokenStatus:
        def __eq__(self, _other):
            raise RuntimeError("rerun status comparison unavailable")

        def __str__(self):
            raise RuntimeError("rerun status text unavailable")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        calls["get_job"] += 1
        if calls["get_job"] == 1:
            return {
                "job_id": job_id,
                "ticker": filename,
                "pipeline_id": "rerun:final_recommendation",
                "status": "running",
            }
        if calls["get_job"] == 2:
            return {
                "job_id": job_id,
                "ticker": filename,
                "pipeline_id": "rerun:final_recommendation",
                "status": BrokenStatus(),
            }
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": "2449_v2_report_20260607_010000.html",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", lambda *_args, **_kwargs: [])

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "2449_v2_report_20260607_010000.html" in response.text


def test_rerun_report_stream_persists_terminal_fallback_with_event_id(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:final_recommendation")
    job_store.update_job(job_id, "done", filename="2449_v2_report_20260607_010000.html")

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )

    assert response.status_code == 200
    assert "id: 2" in response.text
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    assert events[0]["type"] == "done"
    assert events[0]["filename"] == "2449_v2_report_20260607_010000.html"


def test_rerun_report_stream_error_fallback_preserves_source_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    job_store.update_job(job_id, "error", error="worker lost terminal event")

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert error_event["message"] == "worker lost terminal event"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_report_stream_cancelled_fallback_preserves_source_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")
    job_store.update_job(job_id, "cancelled", error="operator cancelled before terminal event")

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert error_event["phase"] == "cancelled"
    assert error_event["message"] == "operator cancelled before terminal event"
    assert error_event["rerun_scope"] == "mode_b"
    assert error_event["source_filename"] == filename


def test_rerun_report_stream_error_fallback_uses_safe_message_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:full_report",
            "status": "error",
            "error": memoryview(b"unsafe terminal error"),
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert error_event["message"] == "報告重跑任務失敗"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_report_stream_cancelled_fallback_uses_safe_message_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:mode_b",
            "status": "cancelled",
            "error": memoryview(b"unsafe cancel message"),
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert error_event["phase"] == "cancelled"
    assert error_event["message"] == "報告重跑任務已取消"
    assert error_event["rerun_scope"] == "mode_b"
    assert error_event["source_filename"] == filename


def test_rerun_report_stream_done_fallback_uses_safe_filename_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:final_recommendation")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": "rerun:final_recommendation",
            "status": "done",
            "filename": memoryview(b"unsafe generated filename"),
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    done_event = next(event for event in events if event["type"] == "done")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert done_event["filename"] is None
    assert done_event["rerun_scope"] == "final_recommendation"
    assert done_event["source_filename"] == filename


def test_rerun_report_stream_empty_scope_fallback_uses_default_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:")
    job_store.update_job(job_id, "error", error="worker lost terminal event")

    client = TestClient(api.app)
    response = client.get(
        f"/api/report/{filename}/rerun/stream",
        params={"job_id": job_id, "last_event_id": 1},
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert response.status_code == 200
    assert "id: 2" in response.text
    assert error_event["message"] == "worker lost terminal event"
    assert error_event["rerun_scope"] == "final_recommendation"
    assert error_event["source_filename"] == filename


def test_rerun_report_stream_malformed_pipeline_id_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    class BrokenPipelineId:
        def __str__(self):
            raise RuntimeError("pipeline id string conversion failed")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": BrokenPipelineId(),
            "status": "running",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 404
    assert response.json()["detail"] == "找不到報告重跑任務"


def test_rerun_report_stream_malformed_ticker_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    class BrokenTicker:
        def __str__(self):
            raise RuntimeError("ticker string conversion failed")

        def __ne__(self, _other):
            raise RuntimeError("ticker comparison failed")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": BrokenTicker(),
            "pipeline_id": "rerun:full_report",
            "status": "running",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 404
    assert response.json()["detail"] == "找不到報告重跑任務"


def test_rerun_progress_event_preserves_mapping_safe_payload(tmp_path, monkeypatch):
    from types import MappingProxyType

    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        MappingProxyType(
            {
                "type": "status",
                "phase": "rerun_refresh_data",
                "message": "完整重跑前正在刷新資料快照...",
                "current": 2,
                "total": 7,
            }
        ),
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["phase"] == "rerun_refresh_data"
    assert events[0]["message"] == "完整重跑前正在刷新資料快照..."
    assert events[0]["current"] == 2
    assert events[0]["total"] == 7
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_preserves_snapshot_safe_nested_payload(tmp_path, monkeypatch):
    from types import MappingProxyType

    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        MappingProxyType(
            {
                "type": "status",
                "phase": "rerun_refresh_data",
                "message": "完整重跑前正在刷新資料快照...",
                "details": MappingProxyType(
                    {
                        "source_audit": (
                            MappingProxyType(
                                {
                                    "source": "market_data",
                                    "provider": "snapshot",
                                    "status": "success",
                                }
                            ),
                        ),
                    }
                ),
            }
        ),
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["details"]["source_audit"][0]["source"] == "market_data"
    assert events[0]["details"]["source_audit"][0]["status"] == "success"
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_falls_back_for_malformed_scalar_progress(tmp_path, monkeypatch):
    import report_rerun_jobs

    class MalformedProgressScalar:
        def __bool__(self):
            raise RuntimeError("truthiness unavailable")

        def __int__(self):
            raise RuntimeError("integer conversion unavailable")

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        MalformedProgressScalar(),
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "progress"
    assert events[0]["current"] == 0
    assert events[0]["total"] == 1
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_scope_for_job_store(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        memoryview(b"full_report"),
        {"type": "status", "phase": "rerun_refresh_data", "message": "刷新資料中"},
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_refresh_data"
    assert events[0]["message"] == "刷新資料中"
    assert events[0]["rerun_scope"] == "final_recommendation"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_control_fields(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": True,
            "phase": memoryview(b"rerun_refresh_data"),
            "level": False,
            "message": "刷新資料中",
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun"
    assert "level" not in events[0]
    assert events[0]["message"] == "刷新資料中"
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_count_fields(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "progress",
            "phase": "rerun_refresh_data",
            "current": True,
            "total": memoryview(b"8"),
            "message": "刷新資料中",
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "progress"
    assert events[0]["phase"] == "rerun_refresh_data"
    assert events[0]["current"] == 0
    assert events[0]["total"] == 0
    assert events[0]["message"] == "刷新資料中"
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_message_field(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "status",
            "phase": "rerun_refresh_data",
            "message": {"text": "刷新資料中"},
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_refresh_data"
    assert events[0]["message"] == ""
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_name_field(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "progress",
            "phase": "rerun_agent",
            "current": 1,
            "total": 3,
            "name": {"label": "Agent 1"},
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "progress"
    assert events[0]["phase"] == "rerun_agent"
    assert events[0]["current"] == 1
    assert events[0]["total"] == 3
    assert events[0]["name"] == ""
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_detail_field(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "status",
            "phase": "rerun_refresh_data",
            "message": "刷新資料中",
            "detail": {"provider": "snapshot"},
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_refresh_data"
    assert events[0]["message"] == "刷新資料中"
    assert events[0]["detail"] == ""
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_agent_num_field(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "status",
            "phase": "rerun_final_agent",
            "message": "重跑最終投資建議 Agent...",
            "agent_num": True,
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_final_agent"
    assert events[0]["message"] == "重跑最終投資建議 Agent..."
    assert events[0]["agent_num"] == 0
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_pipeline_identity_fields(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "status",
            "phase": "rerun_final_agent",
            "message": "重跑最終投資建議 Agent...",
            "pipeline_id": True,
            "pipeline_label": {"label": "模式 B"},
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_final_agent"
    assert events[0]["message"] == "重跑最終投資建議 Agent..."
    assert events[0]["pipeline_id"] == ""
    assert events[0]["pipeline_label"] == ""
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_progress_event_normalizes_malformed_metadata_field(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")
    report_rerun_jobs._append_progress_event(
        job_id,
        filename,
        "full_report",
        {
            "type": "status",
            "phase": "rerun_final_agent",
            "message": "重跑最終投資建議 Agent...",
            "metadata": True,
        },
    )

    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]

    assert events[0]["type"] == "status"
    assert events[0]["phase"] == "rerun_final_agent"
    assert events[0]["message"] == "重跑最終投資建議 Agent..."
    assert events[0]["metadata"] == {}
    assert events[0]["rerun_scope"] == "full_report"
    assert events[0]["source_filename"] == filename


def test_rerun_job_api_key_failure_event_preserves_source_filename(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: False)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "error"
    assert job_store.get_job(job_id)["error"] == report_rerun_jobs.API_KEY_SETUP_MESSAGE
    assert error_event["message"] == report_rerun_jobs.API_KEY_SETUP_MESSAGE
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_job_api_key_failure_normalizes_malformed_source_filename(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: False)
    job_id = job_store.create_job("2449_v2_report_20260606_010000.html", "rerun:full_report")

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            memoryview(b"2449_v2_report_20260606_010000.html"),
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "error"
    assert error_event["message"] == report_rerun_jobs.API_KEY_SETUP_MESSAGE
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == ""


def test_rerun_job_cancelled_exception_uses_safe_message_fallback(tmp_path, monkeypatch):
    import report_rerun_jobs

    class MalformedCancellation(report_rerun_jobs.ReportRerunJobCancelled):
        def __str__(self):
            raise RuntimeError("string conversion unavailable")

    def fake_raise_if_cancelled(_job_id):
        raise MalformedCancellation()

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(report_rerun_jobs, "_raise_if_cancelled", fake_raise_if_cancelled)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "cancelled"
    assert job_store.get_job(job_id)["error"] == "報告重跑任務已取消。"
    assert error_event["phase"] == "cancelled"
    assert error_event["level"] == "warning"
    assert error_event["message"] == "報告重跑任務已取消。"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_job_invalid_scope_persists_terminal_error_event(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:unsupported_scope")

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "unsupported_scope",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "error"
    assert job_store.get_job(job_id)["error"] == "scope must be final_recommendation, full_report, or mode_b"
    assert error_event["status_code"] == 400
    assert error_event["message"] == "scope must be final_recommendation, full_report, or mode_b"
    assert error_event["rerun_scope"] == "unsupported_scope"
    assert error_event["source_filename"] == filename


def test_rerun_job_done_events_preserve_mapping_safe_result_payload(tmp_path, monkeypatch):
    from types import MappingProxyType

    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    generated_filename = "2449_v2_report_20260607_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        return MappingProxyType(
            {
                "filename": generated_filename,
                "md_filename": generated_filename.replace(".html", ".md"),
                "data_filename": generated_filename.replace(".html", ".data.json"),
                "data_trust": MappingProxyType(
                    {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                ),
                "scope_label": "完整重跑同模式報告",
                "partial_rerun": MappingProxyType(
                    {
                        "scope": "full_report",
                        "source_report": filename,
                        "generated_report": generated_filename,
                    }
                ),
                "metadata": MappingProxyType({"pipeline_id": "v2"}),
            }
        )

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    report_done = next(event for event in events if event["type"] == "report_done")
    done = next(event for event in events if event["type"] == "done")

    assert result_filename == generated_filename
    assert report_done["filename"] == generated_filename
    assert report_done["data_trust"]["status"] == "fresh"
    assert report_done["partial_rerun"]["source_report"] == filename
    assert report_done["pipeline_id"] == "v2"
    assert done["data_trust"]["critical_failures"] == []


def test_rerun_job_done_events_normalize_malformed_identity_fields(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        return {
            "filename": True,
            "md_filename": b"2449_v2_report_20260607_010000.md",
            "data_filename": memoryview(b"2449_v2_report_20260607_010000.data.json"),
            "scope_label": False,
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
            "partial_rerun": {"scope": "full_report", "source_report": filename},
            "metadata": {"pipeline_id": True},
        }

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    report_done = next(event for event in events if event["type"] == "report_done")
    done = next(event for event in events if event["type"] == "done")

    assert result_filename == ""
    assert report_done["filename"] == ""
    assert report_done["md_filename"] == ""
    assert report_done["data_filename"] == ""
    assert report_done["scope_label"] == "完整重跑同模式報告"
    assert report_done["pipeline_id"] == ""
    assert done["filename"] == ""
    assert done["scope_label"] == "完整重跑同模式報告"


def test_rerun_job_done_events_normalize_malformed_structured_result_fields(tmp_path, monkeypatch):
    import report_rerun_jobs

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    generated_filename = "2449_v2_report_20260607_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        return {
            "filename": generated_filename,
            "md_filename": generated_filename.replace(".html", ".md"),
            "data_filename": generated_filename.replace(".html", ".data.json"),
            "scope_label": "完整重跑同模式報告",
            "data_trust": True,
            "partial_rerun": True,
            "metadata": {"pipeline_id": "v2"},
        }

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    report_done = next(event for event in events if event["type"] == "report_done")
    done = next(event for event in events if event["type"] == "done")

    assert result_filename == generated_filename
    assert report_done["filename"] == generated_filename
    assert report_done["data_trust"] == {}
    assert report_done["partial_rerun"] == {}
    assert report_done["pipeline_id"] == "v2"
    assert done["data_trust"] == {}


def test_rerun_job_http_exception_uses_safe_detail_fallback(tmp_path, monkeypatch):
    import report_rerun_jobs

    class MalformedErrorDetail:
        def __bool__(self):
            raise RuntimeError("truthiness unavailable")

        def __str__(self):
            raise RuntimeError("string conversion unavailable")

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        raise report_rerun_jobs.HTTPException(status_code=422, detail=MalformedErrorDetail())

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "error"
    assert job_store.get_job(job_id)["error"] == "報告重跑失敗"
    assert error_event["status_code"] == 422
    assert error_event["message"] == "報告重跑失敗"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_job_http_exception_uses_safe_status_code_fallback(tmp_path, monkeypatch):
    import report_rerun_jobs

    class MalformedStatusCode:
        def __int__(self):
            raise RuntimeError("integer conversion unavailable")

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        exc = report_rerun_jobs.HTTPException(status_code=500, detail="上游重跑失敗")
        exc.status_code = MalformedStatusCode()
        raise exc

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    result_filename = asyncio.run(
        report_rerun_jobs.run_report_rerun_job_async(
            job_id,
            filename,
            "full_report",
            output_dir=str(tmp_path),
            pipeline_runner=object(),
            report_renderer=object(),
            refresh_service=object(),
        )
    )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert result_filename == ""
    assert job_store.get_job(job_id)["status"] == "error"
    assert job_store.get_job(job_id)["error"] == "上游重跑失敗"
    assert error_event["status_code"] == 500
    assert error_event["message"] == "上游重跑失敗"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_job_generic_exception_uses_safe_error_event_fallback(tmp_path, monkeypatch):
    import report_rerun_jobs

    class MalformedRuntimeError(RuntimeError):
        def __str__(self):
            raise RuntimeError("string conversion unavailable")

    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(report_rerun_jobs, "has_api_keys", lambda: True)
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:full_report")

    async def fake_rerun_report_analysis(*_args, **_kwargs):
        raise MalformedRuntimeError()

    monkeypatch.setattr(report_rerun_jobs.report_rerun_service, "rerun_report_analysis", fake_rerun_report_analysis)

    with pytest.raises(MalformedRuntimeError):
        asyncio.run(
            report_rerun_jobs.run_report_rerun_job_async(
                job_id,
                filename,
                "full_report",
                output_dir=str(tmp_path),
                pipeline_runner=object(),
                report_renderer=object(),
                refresh_service=object(),
            )
        )
    events = [event["payload"] for event in job_store.get_events_since(job_id, 1)]
    error_event = next(event for event in events if event["type"] == "error")

    assert job_store.get_job(job_id)["status"] == "error"
    assert job_store.get_job(job_id)["error"] == "報告重跑失敗"
    assert error_event["message"] == "報告重跑失敗"
    assert error_event["rerun_scope"] == "full_report"
    assert error_event["source_filename"] == filename


def test_rerun_report_cancel_endpoint_requests_cancel(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")

    client = TestClient(api.app)
    response = client.post(f"/api/report/{filename}/rerun/cancel", params={"job_id": job_id}, headers=mutation_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "cancelling"
    assert job_store.is_job_cancel_requested(job_id) is True


def test_rerun_report_cancel_endpoint_malformed_job_row_returns_not_found(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = "malformed-cancel-job-row"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return ["malformed", candidate_job_id]

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun/cancel", params={"job_id": job_id}, headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的報告重跑任務"}


def test_rerun_report_cancel_endpoint_malformed_pipeline_id_returns_not_found(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")

    class BrokenPipelineId:
        def __str__(self):
            raise RuntimeError("pipeline id string conversion failed")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": filename,
            "pipeline_id": BrokenPipelineId(),
            "status": "running",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun/cancel", params={"job_id": job_id}, headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的報告重跑任務"}


def test_rerun_report_cancel_endpoint_malformed_ticker_returns_not_found(tmp_path, monkeypatch, mutation_headers):
    monkeypatch.setattr(job_store, "TASK_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    filename = "2449_v2_report_20260606_010000.html"
    job_id = job_store.create_job(filename, "rerun:mode_b")

    class BrokenTicker:
        def __str__(self):
            raise RuntimeError("ticker string conversion failed")

        def __ne__(self, _other):
            raise RuntimeError("ticker comparison failed")

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": BrokenTicker(),
            "pipeline_id": "rerun:mode_b",
            "status": "running",
        }

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post(f"/api/report/{filename}/rerun/cancel", params={"job_id": job_id}, headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的報告重跑任務"}


def test_final_rerun_uses_snapshot_rerun_context_without_markdown(tmp_path, monkeypatch):
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    (tmp_path / filename.replace(".html", ".md")).unlink()
    analyses = {str(agent): f"Agent {agent} analysis" for agent in [11, 12, 13, 14, 15]}
    snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline": "v2",
        "generated_at": "2026-06-07T00:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": None, "notes": []},
        "rerun_context": {
            "analyses": analyses,
            "structured_outputs": {"14": {"price_targets": {"基本情境": 273}}},
        },
        "data": {"data_schema_version": 4, "ticker": "2449.TW", "company_name": "京元電子"},
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(json.dumps(snapshot), encoding="utf-8")

    fake_rotator = object()

    async def fake_run_agent(agent_num, data, context, rotator):
        assert rotator is fake_rotator
        context["analyses"][agent_num] = "final recommendation rerun"
        context["structured_outputs"][agent_num] = {"recommendation": {"建議": "持有"}}
        return "final recommendation rerun"

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html='<div class="sidebar-name">京元電子</div>',
                markdown="# report",
                data_snapshot={
                    "snapshot_schema_version": 3,
                    "ticker": "2449.TW",
                    "company_name": "京元電子",
                    "pipeline": request.pipeline_id,
                    "generated_at": "2026-06-07T00:00:00+00:00",
                    "data_schema_version": 4,
                    "source_freshness": {},
                    "source_audit": [],
                    "data_trust": snapshot["data_trust"],
                    "rerun_context": request.context.get("rerun_context", {}),
                    "data": request.context["data"],
                },
            )

    monkeypatch.setattr(report_rerun_service, "KeyRotator", lambda _keys: fake_rotator)
    monkeypatch.setattr(report_rerun_service, "run_agent_with_quality_gates_async", fake_run_agent)
    monkeypatch.setattr(report_rerun_service, "run_final_report_audit", lambda context, append_section=True: {"warnings": []})
    monkeypatch.setattr(report_rerun_service, "parse_structured_data", lambda context: {"recommendation": {"建議": "持有"}})

    result = api_report_service.rerun_report_analysis(
        filename,
        scope="final_recommendation",
        output_dir=str(tmp_path),
        pipeline_runner=object(),
        report_renderer=FakeReportRenderer(),
    )
    import asyncio

    body = asyncio.run(result)

    assert body["success"] is True
    assert body["scope"] == "final_recommendation"
    assert (tmp_path / report_bundle_keys_for_filename(body["filename"]).html_key).exists()


def test_final_rerun_context_normalizes_mapping_safe_snapshot_data(tmp_path):
    from types import MappingProxyType

    filename = "2449_v2_report_20260606_010000.html"
    analyses = {str(agent): f"Agent {agent} analysis" for agent in [11, 12, 13, 14, 15]}
    snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline": "v2",
        "generated_at": "2026-06-07T00:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
        "rerun_context": {
            "analyses": analyses,
            "structured_outputs": {"14": {"price_targets": {"基本情境": 273}}},
        },
        "data": MappingProxyType(
            {
                "data_schema_version": 4,
                "ticker": "2449.TW",
                "company_name": "京元電子",
                "source_audit": (
                    MappingProxyType(
                        {
                            "source": "market_data",
                            "provider": "snapshot",
                            "status": "success",
                        }
                    ),
                ),
                "data_trust": MappingProxyType(
                    {"status": "fresh", "critical_failures": (), "stale_sources": ()}
                ),
            }
        ),
    }

    context, _, _ = report_rerun_service._build_final_rerun_context(filename, snapshot, str(tmp_path))
    context["data"]["source_audit"].append({"source": "rerun", "provider": "pipeline", "status": "success"})

    assert context["data"]["data_trust"]["status"] == "fresh"
    assert context["data"]["source_audit"][-1]["source"] == "rerun"


def test_final_rerun_context_reads_mapping_safe_rerun_context_without_markdown(tmp_path):
    from types import MappingProxyType

    filename = "2449_v2_report_20260606_010000.html"
    analyses = MappingProxyType({str(agent): f"Agent {agent} analysis" for agent in [11, 12, 13, 14, 15]})
    snapshot = MappingProxyType(
        {
            "snapshot_schema_version": 3,
            "ticker": "2449.TW",
            "company_name": "京元電子",
            "pipeline": "v2",
            "generated_at": "2026-06-07T00:00:00+00:00",
            "data_schema_version": 4,
            "source_freshness": {},
            "source_audit": [],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
            "rerun_context": MappingProxyType(
                {
                    "analyses": analyses,
                    "structured_outputs": MappingProxyType({"14": {"price_targets": {"基本情境": 273}}}),
                }
            ),
            "data": MappingProxyType(
                {
                    "data_schema_version": 4,
                    "ticker": "2449.TW",
                    "company_name": "京元電子",
                    "source_audit": [],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": []},
                }
            ),
        }
    )

    context, _, _ = report_rerun_service._build_final_rerun_context(filename, snapshot, str(tmp_path))

    assert context["analyses"][11] == "Agent 11 analysis"
    assert 15 in context["analyses"]
    assert 14 in context["structured_outputs"]


def test_final_rerun_rejects_refreshed_snapshot_that_needs_full_analysis(tmp_path):
    filename = "2449_v2_report_20260606_010000.html"
    write_report_pair(tmp_path, filename, "持有")
    analyses = {str(agent): f"Agent {agent} analysis" for agent in [11, 12, 13, 14, 15]}
    snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2449.TW",
        "company_name": "京元電子",
        "pipeline": "v2",
        "generated_at": "2026-06-08T00:00:00+00:00",
        "conclusion_generated_at": "2026-06-06T00:00:00+00:00",
        "snapshot_refreshed_at": "2026-06-08T00:00:00+00:00",
        "refreshed_without_analysis_rerun": True,
        "decision_validity_status": "needs_rerun",
        "requires_rerun_reason": "資料快照已刷新，但前序分析本文未重新執行。",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "last_market_data_at": None, "notes": []},
        "rerun_context": {
            "analyses": analyses,
            "structured_outputs": {"14": {"price_targets": {"基本情境": 273}}},
        },
        "data": {"data_schema_version": 4, "ticker": "2449.TW", "company_name": "京元電子"},
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(report_rerun_service.HTTPException) as exc_info:
        report_rerun_service._build_final_rerun_context(filename, snapshot, str(tmp_path))

    assert exc_info.value.status_code == 409
    assert "完整重跑" in str(exc_info.value.detail)


def test_parse_agent_sections_from_markdown_supports_final_rerun_context():
    markdown = """# report

## 1. 總經分析 (Agent 11)
總經段落

---

## 2. 商業模式 (Agent 12)
商業模式段落

---

## 來源審計
表格
"""

    sections = api_report_service.parse_agent_sections_from_markdown(markdown)

    assert sections == {11: "總經段落", 12: "商業模式段落"}
