import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_fresh_hold_with_strong_upside_is_calibrated_to_buy():
    from recommendation_calibration import calibrate_recommendation_summary

    calibrated = calibrate_recommendation_summary(
        {
            "recommendation": "持有",
            "current_price": "NT$100",
            "target_12m": "NT$135",
            "confidence": "7/10",
        },
        data_trust={"status": "fresh"},
    )

    assert calibrated["recommendation"] == "買入"
    assert calibrated["original_recommendation"] == "持有"
    assert calibrated["recommendation_calibration"]["status"] == "adjusted"
    assert calibrated["recommendation_calibration"]["expected_return_pct"] == 35.0


def test_partial_high_upside_hold_is_marked_watch_without_auto_upgrade():
    from recommendation_calibration import calibrate_recommendation_summary

    calibrated = calibrate_recommendation_summary(
        {
            "recommendation": "持有",
            "current_price": "NT$100",
            "target_12m": "NT$135",
            "confidence": "7/10",
        },
        data_trust={"status": "partial"},
    )

    assert calibrated["recommendation"] == "持有"
    assert "original_recommendation" not in calibrated
    assert calibrated["recommendation_calibration"]["status"] == "watch"
    assert calibrated["recommendation_calibration"]["calibrated_recommendation"] == "持有"
    assert any("資料可信度" in reason for reason in calibrated["recommendation_calibration"]["reasons"])


def test_bearish_recommendation_with_positive_target_is_neutralized():
    from recommendation_calibration import calibrate_recommendation_summary

    calibrated = calibrate_recommendation_summary(
        {
            "recommendation": "放空",
            "current_price": "NT$100",
            "target_12m": "NT$120",
            "confidence": "8/10",
        },
        data_trust={"status": "fresh"},
    )

    assert calibrated["recommendation"] == "持有"
    assert calibrated["original_recommendation"] == "放空"
    assert calibrated["recommendation_calibration"]["status"] == "adjusted"
    assert any("方向矛盾" in reason for reason in calibrated["recommendation_calibration"]["reasons"])


def test_report_metadata_uses_calibrated_recommendation_for_index_and_tracking(tmp_path):
    from report_index_metadata import build_report_metadata

    filename = "2449_v2_report_20260703_100000.html"
    (tmp_path / filename).write_text(
        '<html><body><div class="sidebar-name">測試公司 / Test Co</div></body></html>',
        encoding="utf-8",
    )
    (tmp_path / filename.replace(".html", ".md")).write_text(
        """# 2449.TW 測試公司 - 報告

## 一頁式摘要
目標價與信心均支持升格。

## 📊 關鍵指標
- **股價:** NT$100

## 🎯 最終投資建議
- **綜合建議:** 持有
- **3個月目標:** NT$110
- **6個月目標:** NT$120
- **12個月目標:** NT$135
- **信心指數:** 7/10
""",
        encoding="utf-8",
    )
    snapshot = {
        "generated_at": "2026-07-03T02:00:00+00:00",
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        "data": {"current_price": 100.0},
    }
    (tmp_path / filename.replace(".html", ".data.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False),
        encoding="utf-8",
    )

    metadata = build_report_metadata(filename, output_dir=str(tmp_path))

    assert metadata["recommendation"]["recommendation"] == "買入"
    assert metadata["recommendation"]["original_recommendation"] == "持有"
    assert metadata["normalized_recommendation"] == "買入"
    assert metadata["decision_tracking"]["recommendation"] == "買入"
    assert metadata["decision_tracking"]["recommendation_calibration"]["status"] == "adjusted"


def test_report_preview_exposes_recommendation_calibration_metric():
    from recommendation_calibration import calibrate_recommendation_summary
    from report_preview import build_report_preview

    recommendation = calibrate_recommendation_summary(
        {
            "recommendation": "持有",
            "current_price": "NT$100",
            "target_12m": "NT$135",
            "confidence": "7/10",
            "summary": "測試摘要。",
        },
        data_trust={"status": "fresh"},
    )

    preview = build_report_preview("v2", "2449.TW", recommendation)

    assert preview["primary"]["value"] == "買入"
    assert {"label": "校準", "value": "持有 → 買入", "tone": "is-neutral"} in preview["metrics"]
