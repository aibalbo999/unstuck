import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import api  # noqa: E402


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

    summary = api.parse_recommendation_summary("2449_v2_report_20260606_010000.html")

    assert summary["recommendation"] == "持有"
    assert summary["target_3m"] == "NT$273"
    assert summary["target_6m"] == "NT$310"
    assert summary["target_12m"] == "NT$350"
    assert summary["confidence"] == "7/10"
    assert "等待回檔" in summary["summary"]
