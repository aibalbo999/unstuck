import asyncio
import json
import os
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
    assert preview["primary"] == {"label": "空方判斷", "value": "強烈放空", "tone": "is-short"}
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
    assert preview["title"] == "2449 極短線交易預覽"
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
    assert [item.force_refresh for item in refresh_options] == [False]
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
    response = client.get(f"/api/report/{filename}/rerun/stream", params={"job_id": job_id})

    assert response.status_code == 200
    assert '"type": "job"' in response.text
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
