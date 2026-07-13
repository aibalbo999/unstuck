import sys
from types import MappingProxyType
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


def test_report_reading_notice_blocks_false_valid_snapshot_integrity():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "verified",
            "valid": False,
            "errors": "snapshot_hash mismatch",
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "品質 gate 未通過" in html
    assert "snapshot_hash mismatch" in html
    assert "品質 gate 未通過" in markdown
    assert "snapshot_hash mismatch" in markdown


def test_report_reading_notice_accepts_mapping_snapshot_integrity_payloads():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity=MappingProxyType(
            {
                "status": "invalid",
                "hash": "actual-hash",
                "expected_hash": "expected-hash",
            }
        ),
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "snapshot_hash mismatch" in html
    assert "品質 gate 未通過" in markdown
    assert "snapshot_hash mismatch" in markdown


def test_report_reading_notice_treats_mapping_quality_gates_as_recorded():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate=MappingProxyType({"verdict": "approved"}),
        content_credibility=MappingProxyType({"status": "passed"}),
        report_conformance=MappingProxyType({"status": "passed"}),
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-passed" in html
    assert "已通過已知檢查" in html
    assert "品質 gate 尚未記錄" not in html
    assert "已通過已知檢查" in markdown
    assert "品質 gate 尚未記錄" not in markdown


def test_report_reading_notice_lets_nested_invalid_snapshot_integrity_override_top_level_verified():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={"status": "verified"},
        data={
            "data_trust": {"status": "fresh"},
            "snapshot_integrity": {
                "status": "invalid",
                "hash": "actual-hash",
                "expected_hash": "expected-hash",
            },
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "snapshot_hash mismatch" in html
    assert "品質 gate 未通過" in markdown
    assert "snapshot_hash mismatch" in markdown


def test_report_reading_notice_preserves_more_specific_nested_invalid_snapshot_integrity_detail():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    specific_error = "provider audit source digest mismatch"
    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "invalid",
            "errors": [generic_error],
        },
        data={
            "data_trust": {"status": "fresh"},
            "snapshot_integrity": {
                "status": "invalid",
                "errors": [specific_error],
            },
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert specific_error in html
    assert generic_error not in html
    assert "品質 gate 未通過" in markdown
    assert specific_error in markdown
    assert generic_error not in markdown


def test_report_reading_notice_derives_snapshot_hash_mismatch_detail_from_hashes():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "invalid",
            "hash": "actual-hash",
            "expected_hash": "expected-hash",
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "snapshot_hash mismatch" in html
    assert "品質 gate 未通過" in markdown
    assert "snapshot_hash mismatch" in markdown


def test_report_reading_notice_prefers_hash_mismatch_over_generic_snapshot_integrity_error():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "invalid",
            "hash": "actual-hash",
            "expected_hash": "expected-hash",
            "errors": [generic_error],
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert "snapshot_hash mismatch" in html
    assert generic_error not in html
    assert "品質 gate 未通過" in markdown
    assert "snapshot_hash mismatch" in markdown
    assert generic_error not in markdown


def test_report_reading_notice_deduplicates_snapshot_integrity_error_details():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    detail = "provider audit source digest mismatch"
    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "invalid",
            "valid": False,
            "errors": [detail, detail],
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert html.count(detail) == 1
    assert "品質 gate 未通過" in markdown
    assert markdown.count(detail) == 1


def test_report_reading_notice_removes_generic_snapshot_integrity_error_when_specific_detail_exists():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    generic_error = "資料快照完整性未通過，不能直接引用報告結論。"
    specific_error = "provider audit source digest mismatch"
    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={
            "status": "invalid",
            "valid": False,
            "errors": [generic_error, specific_error],
        },
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-blocked" in html
    assert specific_error in html
    assert generic_error not in html
    assert "品質 gate 未通過" in markdown
    assert specific_error in markdown
    assert generic_error not in markdown


def test_report_reading_notice_warns_for_unverified_snapshot_integrity():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "approved"},
        content_credibility={"status": "passed"},
        report_conformance={"status": "passed"},
        snapshot_integrity={"status": "unverified", "valid": None},
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)

    assert "report-reading-notice-warning" in html
    assert "品質 gate 有警示" in html
    assert "資料快照完整性" in html
    assert "未驗證" in html
    assert "品質 gate 有警示" in markdown
    assert "資料快照完整性" in markdown
    assert "未驗證" in markdown


def test_report_reading_notice_does_not_promote_partial_gate_records_to_passed():
    from reporting.reading_notice import build_report_reading_notice_html

    html = build_report_reading_notice_html(
        _context(content_credibility={"status": "passed"})
    )

    assert "report-reading-notice-warning" in html
    assert "品質 gate 有警示" in html


def test_report_reading_notice_uses_shared_text_safety_for_quality_gate_statuses():
    from reporting.reading_notice import build_report_reading_notice_html, build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": b"bad-evidence"},
        content_credibility={"status": memoryview(b"bad-content")},
        report_conformance={"status": bytearray(b"bad-conformance")},
    )

    html = build_report_reading_notice_html(context)
    markdown = build_report_reading_notice_markdown(context)
    rendered = html + markdown

    assert "report-reading-notice-warning" in html
    assert "證據抽查" in rendered
    assert "未記錄" in rendered
    assert "bad-evidence" not in rendered
    assert "bad-content" not in rendered
    assert "bad-conformance" not in rendered


def test_report_reading_notice_markdown_collapses_embedded_newlines_in_gate_text():
    from reporting.reading_notice import build_report_reading_notice_markdown

    context = _context(
        evidence_exit_gate={"verdict": "caution\nmanual review"},
        content_credibility={"status": "warning\ncontent"},
        report_conformance={"status": "warning\ncontract"},
        snapshot_integrity={
            "status": "invalid",
            "errors": ["provider detail\nneeds repair"],
        },
    )

    markdown = build_report_reading_notice_markdown(context)

    assert "- **證據抽查:** caution manual review" in markdown
    assert "- **內容一致性:** warning content" in markdown
    assert "- **輸出契約:** warning contract" in markdown
    assert "> 報告存在阻斷問題" in markdown
    assert "provider detail needs repair" in markdown
    assert "caution\nmanual review" not in markdown
    assert "warning\ncontent" not in markdown
    assert "provider detail\nneeds repair" not in markdown
