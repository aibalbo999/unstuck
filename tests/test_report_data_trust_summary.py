import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_data_trust_summary_builds_html_and_markdown_values_safely():
    from reporting.data_trust_summary import build_data_trust_summary

    summary = build_data_trust_summary({
        "data_trust": {
            "status": "partial",
            "last_market_data_at": "2026-06-07T00:00:00\n+00:00",
            "critical_failures": ["market_data"],
            "stale_sources": ["financial_statements"],
            "reason_codes": ["source_error:market_data", "provider_sla_warning_note"],
            "notes": [b"bad-note", "有效資料可信度說明。\n第二行。"],
        }
    })

    assert summary["status"] == "partial"
    assert "部分異常" in summary["status_label"]
    assert summary["notes"] == ["有效資料可信度說明。\n第二行。"]
    assert "市場資料：2026-06-07T00:00:00\n+00:00" in summary["detail_parts"]
    assert "核心異常：市場資料" in summary["detail_parts"]
    assert "過期：年度財報" in summary["detail_parts"]
    assert "原因：來源異常：市場資料、來源穩定度提醒" in summary["detail_parts"]
    assert summary["markdown_last_market_data_at"] == "2026-06-07T00:00:00 +00:00"
    assert summary["markdown_notes"] == ["有效資料可信度說明。 第二行。"]
    assert summary["markdown_reason_labels"] == ["來源異常：市場資料", "來源穩定度提醒"]
    assert summary["markdown_critical_sources"] == ["市場資料"]
    assert summary["markdown_stale_sources"] == ["年度財報"]


def test_data_trust_summary_uses_unknown_snapshot_fallback_notes():
    from reporting.data_trust_summary import build_data_trust_summary

    summary = build_data_trust_summary({})

    assert summary["status"] == "unknown"
    assert summary["notes"]
    assert summary["detail_parts"] == ["原因：未記錄報告資料狀態"]


def test_data_trust_summary_drops_missing_text_tokens_from_reason_labels():
    from reporting.data_trust_summary import build_data_trust_summary

    summary = build_data_trust_summary({
        "data_trust": {
            "status": "partial",
            "reason_codes": [
                "NaN",
                "source_error:Infinity",
                "source_stale:-Infinity",
                "optional_source_error:N/A",
                "provider_sla_warning_note",
            ],
            "notes": ["有效資料可信度說明。"],
        }
    })

    rendered_reasons = "\n".join(summary["detail_parts"] + summary["markdown_reason_labels"]).lower()

    assert "來源異常" in rendered_reasons
    assert "來源過期" in rendered_reasons
    assert "補充來源異常" in rendered_reasons
    assert "來源穩定度提醒" in rendered_reasons
    assert "nan" not in rendered_reasons
    assert "infinity" not in rendered_reasons
    assert "n/a" not in rendered_reasons
