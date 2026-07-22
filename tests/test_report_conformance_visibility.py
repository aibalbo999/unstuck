import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.conformance_visibility import missing_visible_markers  # noqa: E402
from reporting.mode_templates import get_report_template_profile  # noqa: E402


def _conforming_artifacts():
    html = """
    <section>本報告資料可信度</section>
    <section>執行邏輯與模型檢查</section>
    <section>報告模板與閱讀路徑</section>
    <section>一頁式摘要</section>
    <section>長線投資論文與決策紀律</section>
    <section>關鍵數據來源對照</section>
    <section>來源審計</section>
    <section>最終投資建議</section>
    """
    markdown = """
## 本報告資料可信度
## 執行邏輯與模型檢查
## 報告模板與閱讀路徑
## 一頁式摘要
## 長線投資論文與決策紀律
## 關鍵數據來源對照
## 來源審計
## 🎯 最終投資建議
"""
    return html, markdown


def test_conformance_visibility_passes_when_required_sections_are_visible():
    html, markdown = _conforming_artifacts()

    assert missing_visible_markers(html, markdown, get_report_template_profile("v1")) == []


def test_conformance_visibility_reports_required_and_mode_specific_missing_sections():
    html = """
    <section>本報告資料可信度</section>
    <section>執行邏輯與模型檢查</section>
    <section>報告模板與閱讀路徑</section>
    <section>事件波段摘要</section>
    <section>來源審計</section>
    <section>極短線交易計畫</section>
    """
    markdown = """
## 本報告資料可信度
## 執行邏輯與模型檢查
## 報告模板與閱讀路徑
## 事件波段摘要
## 來源審計
## 極短線交易計畫
"""

    missing = missing_visible_markers(html, markdown, get_report_template_profile("v4"))

    assert {"id": "source_matrix", "label": "關鍵數據來源對照"} in missing
    assert {"id": "decision_discipline", "label": "交易計畫與風控紀律"} in missing
    assert {"id": "decision", "label": "極短線交易計畫"} not in missing


def test_conformance_visibility_uses_safe_text_for_malformed_artifacts():
    class MalformedText:
        def __str__(self):
            raise RuntimeError("artifact text unavailable")

    missing = missing_visible_markers(MalformedText(), MalformedText(), get_report_template_profile("v1"))

    assert {"id": "data_trust", "label": "本報告資料可信度"} in missing
    assert {"id": "decision", "label": "最終投資建議"} in missing


def test_conformance_visibility_ignores_missing_text_token_profile_headings():
    html, markdown = _conforming_artifacts()

    missing = missing_visible_markers(
        html,
        markdown,
        {
            "summary_heading": "NaN",
            "decision_heading": "Infinity",
            "discipline_heading": "N/A",
        },
    )

    assert missing == []
