import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _context(**overrides):
    context = {
        "data": {"data_trust": {"status": "fresh"}},
    }
    context.update(overrides)
    return context


def test_report_reading_notice_defaults_to_manual_review_when_quality_gates_are_missing():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context()

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-pending" in html
    assert "報告使用範圍與判讀限制" in html
    assert "品質 gate 尚未記錄" in html
    assert "請勿把結論當成可執行指令" in html
    assert "## 報告使用範圍與判讀限制" in markdown
    assert "品質 gate 尚未記錄" in markdown
    assert "請勿把結論當成可執行指令" in markdown


def test_report_reading_notice_surfaces_blocked_quality_status():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "rejected"},
        content_credibility={"status": "blocked"},
        report_conformance={"status": "blocked"},
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "品質 gate 未通過" in html
    assert "先處理品質警示，再引用報告結論" in html
    assert "證據抽查" in html
    assert "輸出契約" in markdown
    assert "品質 gate 未通過" in markdown
    assert "先處理品質警示，再引用報告結論" in markdown


def test_report_reading_notice_explains_that_passed_checks_are_not_an_investment_guarantee():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-passed" in html
    assert "已通過已知檢查" in html
    assert "不代表投資語意一定正確" in html
    assert "已通過已知檢查" in markdown
    assert "不代表投資語意一定正確" in markdown


def test_report_reading_notice_does_not_promote_partial_gate_records_to_passed():
    from reporting.reading_notice import build_report_reading_notice_html

    html = build_report_reading_notice_html(
        _context(content_credibility={"status": "passed"})
    )

    assert "report-reading-notice-warning" in html
    assert "品質 gate 有警示" in html
